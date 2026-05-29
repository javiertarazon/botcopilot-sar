from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any, Dict

import ccxt.async_support as ccxt_async

from .models import Fill, OrderRequest


@dataclass
class CCXTBrokerConfig:
    exchange_name: str
    api_key: str = ""
    api_secret: str = ""
    sandbox: bool = False
    timeout: int = 30_000
    enable_rate_limit: bool = True


class CCXTBroker:
    """
    Broker live mínimo basado en CCXT.

    Implementa market orders y asume spot long-only (cierre vendiendo).
    """

    def __init__(self, config: CCXTBrokerConfig):
        self.config = config
        self.exchange: Optional[Any] = None

    async def initialize(self) -> None:
        exchange_class = getattr(ccxt_async, self.config.exchange_name)
        self.exchange = exchange_class(
            {
                "apiKey": self.config.api_key or "",
                "secret": self.config.api_secret or "",
                "sandbox": self.config.sandbox,
                "timeout": self.config.timeout,
                "enableRateLimit": self.config.enable_rate_limit,
            }
        )
        await self.exchange.load_markets()

    async def close(self) -> None:
        if self.exchange is not None:
            await self.exchange.close()
            self.exchange = None

    async def place_market_order(self, req: OrderRequest) -> Fill:
        if self.exchange is None:
            raise RuntimeError("CCXTBroker no inicializado")

        if req.order_type != "market":
            raise ValueError("Solo soporta órdenes market")

        order = await self.exchange.create_order(req.symbol, "market", req.side, req.quantity)
        price = float(order.get("average") or order.get("price") or 0.0)
        fee_cost = 0.0
        fee = order.get("fee")
        if isinstance(fee, dict) and "cost" in fee and fee["cost"] is not None:
            try:
                fee_cost = float(fee["cost"])
            except (TypeError, ValueError):
                fee_cost = 0.0

        return Fill(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            price=price,
            fee=fee_cost,
            timestamp=datetime.now(timezone.utc),
            order_id=str(order.get("id")) if order.get("id") is not None else None,
            metadata={"ccxt_order": order, **(req.metadata or {})},
        )

    async def fetch_balance(self) -> Dict[str, Any]:
        if self.exchange is None:
            raise RuntimeError("CCXTBroker no inicializado")
        return await self.exchange.fetch_balance()

