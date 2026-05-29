from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class PaperPosition:
    symbol: str
    side: str  # "long" | "short"
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperTrade:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl_quote: float
    reason: str
    meta: Dict[str, Any] = field(default_factory=dict)


class PaperBroker:
    """
    Broker simple de paper trading:
    - Mantiene balance en moneda quote (por defecto USDT)
    - Solo permite 1 posición abierta por símbolo
    - Cierra por stop-loss / take-profit cuando el precio cruza el nivel
    """

    def __init__(self, initial_quote_balance: float = 10_000.0, quote_currency: str = "USDT"):
        self.quote_currency = quote_currency
        self.quote_balance = float(initial_quote_balance)
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: list[PaperTrade] = []

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        return self.positions.get(symbol)

    def open_market(
        self,
        symbol: str,
        side: str,
        price: float,
        quote_amount: float,
        now: Optional[datetime] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> PaperPosition:
        if symbol in self.positions:
            raise ValueError(f"Position already open for {symbol}")
        if quote_amount <= 0:
            raise ValueError("quote_amount must be > 0")
        if price <= 0:
            raise ValueError("price must be > 0")
        if quote_amount > self.quote_balance:
            raise ValueError("Insufficient quote balance")

        side = side.lower()
        if side not in ("long", "short"):
            raise ValueError("side must be 'long' or 'short'")

        quantity = float(quote_amount) / float(price)
        now = now or datetime.utcnow()

        self.quote_balance -= float(quote_amount)
        position = PaperPosition(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=float(price),
            entry_time=now,
            stop_loss=stop_loss,
            take_profit=take_profit,
            meta=meta or {},
        )
        self.positions[symbol] = position
        return position

    def close_market(
        self,
        symbol: str,
        price: float,
        reason: str,
        now: Optional[datetime] = None,
    ) -> PaperTrade:
        position = self.positions.pop(symbol, None)
        if position is None:
            raise ValueError(f"No open position for {symbol}")
        if price <= 0:
            raise ValueError("price must be > 0")

        now = now or datetime.utcnow()
        entry_notional = position.quantity * position.entry_price
        exit_notional = position.quantity * float(price)

        if position.side == "long":
            pnl_quote = exit_notional - entry_notional
            self.quote_balance += exit_notional
        else:
            pnl_quote = entry_notional - exit_notional
            # Short simulado: devolvemos notional inicial + PnL
            self.quote_balance += entry_notional + pnl_quote

        trade = PaperTrade(
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=float(price),
            entry_time=position.entry_time,
            exit_time=now,
            pnl_quote=float(pnl_quote),
            reason=reason,
            meta=position.meta,
        )
        self.trades.append(trade)
        return trade

    def on_price_update(self, symbol: str, price: float, now: Optional[datetime] = None) -> Optional[PaperTrade]:
        position = self.positions.get(symbol)
        if position is None:
            return None

        if position.side == "long":
            if position.take_profit is not None and price >= position.take_profit:
                return self.close_market(symbol, price, reason="take_profit", now=now)
            if position.stop_loss is not None and price <= position.stop_loss:
                return self.close_market(symbol, price, reason="stop_loss", now=now)
        else:
            if position.take_profit is not None and price <= position.take_profit:
                return self.close_market(symbol, price, reason="take_profit", now=now)
            if position.stop_loss is not None and price >= position.stop_loss:
                return self.close_market(symbol, price, reason="stop_loss", now=now)
        return None

