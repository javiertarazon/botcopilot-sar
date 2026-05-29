from datetime import datetime, timezone

import pytest

from descarga_datos.trading.paper_broker import PaperBroker


def test_paper_broker_long_take_profit_closes():
    broker = PaperBroker(initial_quote_balance=1000.0)
    now = datetime.now(timezone.utc)

    broker.open_market(
        symbol="BTC/USDT",
        side="long",
        price=100.0,
        quote_amount=100.0,
        now=now,
        stop_loss=90.0,
        take_profit=110.0,
    )

    trade = broker.on_price_update("BTC/USDT", 110.0, now=now)
    assert trade is not None
    assert trade.reason == "take_profit"
    assert trade.pnl_quote == pytest.approx(10.0)


def test_paper_broker_short_stop_loss_closes():
    broker = PaperBroker(initial_quote_balance=1000.0)
    now = datetime.now(timezone.utc)

    broker.open_market(
        symbol="BTC/USDT",
        side="short",
        price=100.0,
        quote_amount=100.0,
        now=now,
        stop_loss=110.0,
        take_profit=90.0,
    )

    trade = broker.on_price_update("BTC/USDT", 110.0, now=now)
    assert trade is not None
    assert trade.reason == "stop_loss"
    assert trade.pnl_quote == pytest.approx(-10.0)


def test_paper_broker_rejects_insufficient_balance():
    broker = PaperBroker(initial_quote_balance=50.0)
    with pytest.raises(ValueError, match="Insufficient quote balance"):
        broker.open_market(symbol="BTC/USDT", side="long", price=100.0, quote_amount=100.0)
