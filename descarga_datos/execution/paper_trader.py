from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd

from risk_management.risk_management import AdvancedRiskManager
from .paper_broker import PaperBroker, PaperBrokerConfig


@dataclass
class PaperTradingConfig:
    initial_capital: float
    commission_percent: float
    slippage_percent: float
    allow_short: bool = True


def _conservative_exit_price_for_bar(
    position_side: str,
    bar_open: float,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
) -> Optional[float]:
    """
    Decide si la barra toca SL/TP y retorna un precio de salida conservador.
    Regla: si SL y TP se tocan en la misma barra, prioriza SL.
    """
    if position_side == "long":
        if stop_loss is not None and bar_low <= stop_loss:
            return stop_loss
        if take_profit is not None and bar_high >= take_profit:
            return take_profit
        return None

    # short
    if stop_loss is not None and bar_high >= stop_loss:
        return stop_loss
    if take_profit is not None and bar_low <= take_profit:
        return take_profit
    return None


def _configure_risk_manager(rm: AdvancedRiskManager, config) -> None:
    # Mapear config.yaml (risk.risk_percent) -> risk_config.risk_per_trade (0..1)
    if hasattr(config, "risk"):
        risk_percent = getattr(config.risk, "risk_percent", 2.0)
        try:
            rm.risk_config.risk_per_trade = float(risk_percent) / 100.0
        except (TypeError, ValueError):
            pass
        max_dd = getattr(config.risk, "max_drawdown_limit", 20.0)
        try:
            rm.risk_config.max_drawdown = float(max_dd) / 100.0
        except (TypeError, ValueError):
            pass


def run_paper_trading_for_symbol(
    symbol: str,
    strategy: Any,
    data: pd.DataFrame,
    config: Any,
    logger: Any,
    allow_short: bool = True,
) -> Dict[str, Any]:
    """
    Simula ejecución "en streaming" (paper) sobre datos históricos ya descargados.
    """
    if data is None or data.empty:
        return {}

    rm = AdvancedRiskManager()
    _configure_risk_manager(rm, config)

    broker = PaperBroker(
        PaperBrokerConfig(
            initial_cash=float(config.backtesting.initial_capital),
            commission_rate=float(config.backtesting.commission) / 100.0,
            slippage_bps=float(config.backtesting.slippage) * 100.0,
            allow_short=allow_short,
        )
    )

    signals_df = strategy.calculate_signals(data.copy())
    if "buy_signal" not in signals_df.columns or "sell_signal" not in signals_df.columns:
        raise RuntimeError("La estrategia no generó buy_signal/sell_signal")

    trades: List[Dict[str, Any]] = []
    equity_curve: List[float] = [broker.cash]
    current_position_entry = None

    # Usar barras cerradas: empezamos desde i=1 para poder usar shift() en señales
    for i in range(1, len(signals_df)):
        bar = signals_df.iloc[i]
        ts = bar.get("timestamp")
        if isinstance(ts, (int, float)):
            timestamp = datetime.fromtimestamp(int(ts))
        elif isinstance(ts, pd.Timestamp):
            timestamp = ts.to_pydatetime()
        else:
            timestamp = datetime.now()

        price_open = float(bar["open"])
        price_high = float(bar["high"])
        price_low = float(bar["low"])
        price_close = float(bar["close"])

        pos = broker.get_position(symbol)
        if pos is not None:
            exit_price = _conservative_exit_price_for_bar(
                pos.side,
                price_open,
                price_high,
                price_low,
                price_close,
                pos.stop_loss,
                pos.take_profit,
            )
            if exit_price is not None:
                close_fill = broker.close_position(symbol, exit_price, timestamp, metadata={"reason": "sl_tp"})
                pnl = (close_fill.price - pos.entry_price) * pos.quantity if pos.side == "long" else (pos.entry_price - close_fill.price) * pos.quantity
                trades.append(
                    {
                        "entry_time": pos.entry_time.isoformat(),
                        "exit_time": timestamp.isoformat(),
                        "entry_price": pos.entry_price,
                        "exit_price": close_fill.price,
                        "quantity": pos.quantity,
                        "side": "buy" if pos.side == "long" else "sell",
                        "pnl": pnl,
                    }
                )
                current_position_entry = None

        # Señales de entrada/salida
        pos = broker.get_position(symbol)
        buy_signal = bool(bar["buy_signal"])
        sell_signal = bool(bar["sell_signal"])

        # Si hay posición, permitir cierre por señal opuesta
        if pos is not None:
            if (pos.side == "long" and sell_signal) or (pos.side == "short" and buy_signal):
                close_fill = broker.close_position(symbol, price_close, timestamp, metadata={"reason": "signal_flip"})
                pnl = (close_fill.price - pos.entry_price) * pos.quantity if pos.side == "long" else (pos.entry_price - close_fill.price) * pos.quantity
                trades.append(
                    {
                        "entry_time": pos.entry_time.isoformat(),
                        "exit_time": timestamp.isoformat(),
                        "entry_price": pos.entry_price,
                        "exit_price": close_fill.price,
                        "quantity": pos.quantity,
                        "side": "buy" if pos.side == "long" else "sell",
                        "pnl": pnl,
                    }
                )
                current_position_entry = None

        pos = broker.get_position(symbol)
        if pos is None:
            if buy_signal:
                # Calcular SL/TP desde la estrategia en la barra actual
                stop_loss = float(strategy.calculate_stop_loss(signals_df.iloc[i : i + 1], 1).iloc[0])
                take_profit = float(strategy.calculate_take_profit(signals_df.iloc[i : i + 1], 1).iloc[0])
                size_result = rm.calculate_position_size(symbol, price_close, stop_loss, signal_strength=1.0, atr_value=float(bar.get("atr", 0) or 0))
                qty = float(size_result.recommended_size)
                if qty > 0:
                    broker.open_position(symbol, "long", qty, price_close, timestamp, stop_loss=stop_loss, take_profit=take_profit)
                    current_position_entry = {"time": timestamp, "price": price_close, "qty": qty, "side": "long"}
            elif sell_signal and allow_short:
                stop_loss = float(strategy.calculate_stop_loss(signals_df.iloc[i : i + 1], -1).iloc[0])
                take_profit = float(strategy.calculate_take_profit(signals_df.iloc[i : i + 1], -1).iloc[0])
                size_result = rm.calculate_position_size(symbol, price_close, stop_loss, signal_strength=1.0, atr_value=float(bar.get("atr", 0) or 0))
                qty = float(size_result.recommended_size)
                if qty > 0:
                    broker.open_position(symbol, "short", qty, price_close, timestamp, stop_loss=stop_loss, take_profit=take_profit)
                    current_position_entry = {"time": timestamp, "price": price_close, "qty": qty, "side": "short"}

        # Equity mark-to-market
        pos = broker.get_position(symbol)
        mtm = broker.cash
        if pos is not None:
            if pos.side == "long":
                mtm += pos.quantity * price_close
            else:
                mtm -= pos.quantity * price_close
        equity_curve.append(mtm)

    total_pnl = sum(t["pnl"] for t in trades)
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t["pnl"] > 0])
    win_rate = (winning_trades / total_trades) if total_trades else 0.0
    max_drawdown = 0.0
    if equity_curve:
        eq = pd.Series(equity_curve, dtype=float)
        peak = eq.expanding().max()
        dd = (eq - peak)
        max_drawdown = float(abs(dd.min())) if not dd.empty else 0.0

    logger.info(f"[PAPER] {symbol}: trades={total_trades} pnl={total_pnl:.2f} win_rate={win_rate*100:.1f}%")

    return {
        "symbol": symbol,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "max_drawdown": max_drawdown,
        "trades": trades,
        "equity_curve": equity_curve,
    }

