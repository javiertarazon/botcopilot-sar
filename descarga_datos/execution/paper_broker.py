from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, List

from .models import Fill, OpenPosition, OrderRequest


@dataclass
class PaperBrokerConfig:
    initial_cash: float = 10_000.0
    commission_rate: float = 0.001  # 0.1%
    slippage_bps: float = 5.0  # 5 bps = 0.05%
    allow_short: bool = True


class PaperBroker:
    """
    Broker de paper trading:
    - Ejecución a precio indicado (típicamente close/stop/tp) con slippage + comisión.
    - Mantiene cash, equity y posiciones simples por símbolo (1 posición por símbolo).
    """

    def __init__(self, config: PaperBrokerConfig):
        self.config = config
        self.cash = float(config.initial_cash)
        self.positions: Dict[str, OpenPosition] = {}
        self.fills: List[Fill] = []

    def get_position(self, symbol: str) -> Optional[OpenPosition]:
        return self.positions.get(symbol)

    def _apply_slippage(self, side: str, price: float) -> float:
        slip = (self.config.slippage_bps / 10_000.0) * price
        # Buy pays more, sell receives less
        return price + slip if side == "buy" else price - slip

    def _fee(self, notional: float) -> float:
        return abs(notional) * self.config.commission_rate

    def place_market_order(self, req: OrderRequest, price: float, timestamp: datetime) -> Fill:
        if req.quantity <= 0:
            raise ValueError("quantity debe ser > 0")

        fill_price = self._apply_slippage(req.side, float(price))
        notional = req.quantity * fill_price
        fee = self._fee(notional)

        # Long-only cash management (paper soporta short, pero solo ajusta cash de forma simple)
        if req.side == "buy":
            self.cash -= (notional + fee)
        else:
            self.cash += (notional - fee)

        fill = Fill(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            price=fill_price,
            timestamp=timestamp,
            fee=fee,
            metadata=req.metadata,
        )
        self.fills.append(fill)
        return fill

    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        timestamp: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> Fill:
        if symbol in self.positions:
            raise RuntimeError(f"Ya existe una posición abierta para {symbol}")

        if side == "short" and not self.config.allow_short:
            raise RuntimeError("Short no permitido en paper broker (config.allow_short=false)")

        order_side = "buy" if side == "long" else "sell"
        fill = self.place_market_order(
            OrderRequest(symbol=symbol, side=order_side, quantity=quantity, metadata=metadata or {}),
            price=price,
            timestamp=timestamp,
        )

        self.positions[symbol] = OpenPosition(
            symbol=symbol,
            side=side,  # long/short
            quantity=quantity,
            entry_price=fill.price,
            entry_time=timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata or {},
        )
        return fill

    def close_position(self, symbol: str, price: float, timestamp: datetime, metadata: Optional[dict] = None) -> Fill:
        pos = self.positions.get(symbol)
        if not pos:
            raise RuntimeError(f"No hay posición abierta para {symbol}")

        order_side = "sell" if pos.side == "long" else "buy"
        fill = self.place_market_order(
            OrderRequest(symbol=symbol, side=order_side, quantity=pos.quantity, metadata=metadata or {}),
            price=price,
            timestamp=timestamp,
        )

        del self.positions[symbol]
        return fill

