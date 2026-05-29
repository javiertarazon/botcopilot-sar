from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Dict, Any


Side = Literal["buy", "sell"]
PositionSide = Literal["long", "short"]


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Side
    quantity: float
    order_type: Literal["market"] = "market"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    quantity: float
    price: float
    timestamp: datetime
    fee: float = 0.0
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenPosition:
    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

