#!/usr/bin/env python3
"""
Paper trading sobre datos de OKX (CCXT) con la estrategia unificada UT Bot + PSAR.

Objetivo:
- Usar OKX vía CCXT para datos de mercado
- Ejecutar un broker de paper trading local (no envía órdenes)
- Exponer un análisis de oportunidad (signal + score + SL/TP sugeridos)
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import ccxt

# Imports del proyecto (ejecución desde repo root o desde descarga_datos/)
import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)
sys.path.append(project_root)
sys.path.append(parent_root)

from config.config_loader import load_config_from_yaml
from strategies.unified_ut_bot_strategy import UnifiedUTBotPSARStrategy
from trading.paper_broker import PaperBroker


def _build_okx_client(config, enable_sandbox: bool) -> ccxt.okx:
    ex_cfg = config.exchanges.get("okx")
    client = ccxt.okx(
        {
            "enableRateLimit": True,
            "apiKey": getattr(ex_cfg, "api_key", "") if ex_cfg else "",
            "secret": getattr(ex_cfg, "api_secret", "") if ex_cfg else "",
            "password": getattr(ex_cfg, "password", "") if ex_cfg else "",
            "timeout": getattr(ex_cfg, "timeout", 30000) if ex_cfg else 30000,
        }
    )
    if enable_sandbox and hasattr(client, "set_sandbox_mode"):
        client.set_sandbox_mode(True)
    return client


def _ohlcv_to_df(ohlcv: list[list[float]]) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp")
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paper trading con OKX (CCXT)")
    parser.add_argument("--config", default=None, help="Ruta a config.yaml (opcional)")
    parser.add_argument("--symbol", default="BTC/USDT", help="Símbolo (ej: BTC/USDT)")
    parser.add_argument("--timeframe", default="1h", help="Timeframe CCXT (ej: 1m, 5m, 1h)")
    parser.add_argument("--candles", type=int, default=300, help="Número de velas a descargar")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Segundos entre iteraciones")
    parser.add_argument("--max-iterations", type=int, default=1, help="Iteraciones (1 = single-shot)")
    parser.add_argument("--initial-usdt", type=float, default=10_000.0, help="Balance inicial en USDT")
    parser.add_argument("--quote-per-trade", type=float, default=250.0, help="USDT por trade (paper)")
    parser.add_argument("--min-score", type=float, default=0.65, help="Score mínimo para abrir posición")
    parser.add_argument("--allow-short", action="store_true", help="Permitir abrir shorts en paper")
    parser.add_argument("--sandbox", action="store_true", help="Usar sandbox/demotrading en OKX (solo endpoints)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config_from_yaml(args.config)

    okx = _build_okx_client(config, enable_sandbox=args.sandbox)
    try:
        okx.load_markets()
    except Exception as exc:
        print(f"ERROR: no se pudo conectar a OKX para cargar mercados: {exc}")
        print("Sugerencias: verifica conectividad/DNS, o ejecuta en un entorno con acceso a https://www.okx.com.")
        return 2

    strategy = UnifiedUTBotPSARStrategy()
    broker = PaperBroker(initial_quote_balance=args.initial_usdt, quote_currency="USDT")

    iterations = 0
    while True:
        iterations += 1
        now = datetime.now(timezone.utc)

        try:
            ohlcv = okx.fetch_ohlcv(args.symbol, timeframe=args.timeframe, limit=args.candles)
        except Exception as exc:
            print(f"ERROR: no se pudo descargar OHLCV de OKX: {exc}")
            return 2
        df = _ohlcv_to_df(ohlcv)

        analysis = strategy.analyze_latest(df, args.symbol)
        last_price = float(analysis["price"])

        closed = broker.on_price_update(args.symbol, last_price, now=now)
        if closed:
            print(f"[{now.isoformat()}] CLOSE {closed.symbol} {closed.side} pnl={closed.pnl_quote:.2f} reason={closed.reason}")

        position = broker.get_position(args.symbol)
        signal: Optional[str] = analysis.get("signal")
        score = float(analysis.get("score", 0.0) or 0.0)

        print(
            f"[{now.isoformat()}] {args.symbol} price={last_price:.4f} signal={signal} score={score:.2f} "
            f"regime={analysis.get('regime')}"
        )

        if position is None and signal and score >= args.min_score:
            if signal == "sell" and not args.allow_short:
                print(f"[{now.isoformat()}] SKIP short disabled")
            else:
                side = "long" if signal == "buy" else "short"
                broker.open_market(
                    symbol=args.symbol,
                    side=side,
                    price=last_price,
                    quote_amount=min(args.quote_per_trade, broker.quote_balance),
                    now=now,
                    stop_loss=analysis.get("stop_loss"),
                    take_profit=analysis.get("take_profit"),
                    meta={"score": score, "reasons": analysis.get("reasons", [])},
                )
                print(
                    f"[{now.isoformat()}] OPEN {args.symbol} {side} quote={args.quote_per_trade:.2f} "
                    f"sl={analysis.get('stop_loss')} tp={analysis.get('take_profit')}"
                )

        if args.max_iterations > 0 and iterations >= args.max_iterations:
            break
        time.sleep(max(1, args.poll_seconds))

    print(f"Final USDT balance: {broker.quote_balance:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
