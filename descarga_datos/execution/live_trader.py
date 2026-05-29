from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd

from risk_management.risk_management import AdvancedRiskManager
from utils.technical_indicators_pipeline import calculate_technical_indicators
from .ccxt_broker import CCXTBroker, CCXTBrokerConfig
from .models import OrderRequest


@dataclass
class LiveTradingConfig:
    symbol: str
    timeframe: str
    poll_seconds: int = 30
    allow_short: bool = False  # spot por defecto


def _configure_risk_manager(rm: AdvancedRiskManager, config) -> None:
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


async def run_live_trading(
    strategy: Any,
    config: Any,
    logger: Any,
    live: LiveTradingConfig,
) -> Dict[str, Any]:
    """
    Loop de trading live (polling) con CCXT:
    - Descarga OHLCV del símbolo
    - Calcula indicadores necesarios
    - Genera señales con la estrategia
    - Ejecuta market orders (long-only por defecto)
    """
    exchange_name = str(getattr(config, "active_exchange", "bybit"))
    exchange_cfg = config.exchanges.get(exchange_name)
    if exchange_cfg is None or not getattr(exchange_cfg, "enabled", False):
        raise RuntimeError(f"Exchange activo no habilitado en config: {exchange_name}")

    broker = CCXTBroker(
        CCXTBrokerConfig(
            exchange_name=exchange_name,
            api_key=getattr(exchange_cfg, "api_key", "") or "",
            api_secret=getattr(exchange_cfg, "api_secret", "") or "",
            sandbox=bool(getattr(exchange_cfg, "sandbox", False)),
            timeout=int(getattr(exchange_cfg, "timeout", 30_000)),
        )
    )

    rm = AdvancedRiskManager()
    _configure_risk_manager(rm, config)

    await broker.initialize()
    logger.info(f"[LIVE] Iniciado en {exchange_name} symbol={live.symbol} timeframe={live.timeframe}")

    position_open = False
    last_signal_ts: Optional[pd.Timestamp] = None

    try:
        while True:
            # OHLCV: timestamp(ms), o,h,l,c,v
            ohlcv = await broker.exchange.fetch_ohlcv(live.symbol, timeframe=live.timeframe, limit=250)
            if not ohlcv:
                await asyncio.sleep(live.poll_seconds)
                continue

            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

            df = calculate_technical_indicators(df)

            signals_df = strategy.calculate_signals(df.copy())
            if len(signals_df) < 3:
                await asyncio.sleep(live.poll_seconds)
                continue

            # Usar última vela cerrada (penúltima)
            bar = signals_df.iloc[-2]
            bar_ts = bar["timestamp"]
            if isinstance(bar_ts, pd.Timestamp) and last_signal_ts is not None and bar_ts <= last_signal_ts:
                await asyncio.sleep(live.poll_seconds)
                continue

            buy_signal = bool(bar.get("buy_signal", False))
            sell_signal = bool(bar.get("sell_signal", False))
            last_signal_ts = bar_ts if isinstance(bar_ts, pd.Timestamp) else None

            price = float(bar["close"])

            if not position_open and buy_signal:
                stop_loss = float(strategy.calculate_stop_loss(signals_df.iloc[-2:-1], 1).iloc[0])
                size = rm.calculate_position_size(live.symbol, price, stop_loss, signal_strength=1.0, atr_value=float(bar.get("atr", 0) or 0))
                qty = float(size.recommended_size)
                if qty <= 0:
                    logger.warning("[LIVE] Señal buy pero qty=0 (riesgo/limites)")
                else:
                    fill = await broker.place_market_order(OrderRequest(symbol=live.symbol, side="buy", quantity=qty))
                    position_open = True
                    logger.info(f"[LIVE] BUY {live.symbol} qty={qty} price={fill.price}")

            elif position_open and sell_signal:
                # Para spot long-only: vender para cerrar. (qty exacto debería venir de estado real)
                # Aquí usamos el último qty recomendado como aproximación mínima.
                # Recomendado: integrar fetch_positions / cartera real.
                logger.info(f"[LIVE] SELL signal {live.symbol} (cierre market).")
                # Intentar vender todo el balance base si el exchange lo permite
                qty = None
                try:
                    bal = await broker.fetch_balance()
                    base = live.symbol.split("/")[0]
                    free = bal.get("free", {}).get(base)
                    if free is not None:
                        qty = float(free)
                except Exception as e:
                    logger.warning(f"[LIVE] No se pudo inferir qty desde balance: {e}")

                if qty is None or qty <= 0:
                    logger.warning("[LIVE] No se pudo cerrar: qty desconocido (configurar balance/posición).")
                else:
                    fill = await broker.place_market_order(OrderRequest(symbol=live.symbol, side="sell", quantity=qty))
                    position_open = False
                    logger.info(f"[LIVE] SELL {live.symbol} qty={qty} price={fill.price}")

            await asyncio.sleep(live.poll_seconds)

    finally:
        await broker.close()

