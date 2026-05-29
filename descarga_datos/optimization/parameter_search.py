from __future__ import annotations

import io
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from backtesting.backtester import AdvancedBacktester
from strategies.ut_bot_psar import UTBotPSARStrategy
from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy
from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy


DEFAULT_SOL_1H_CSV_URL = (
    "https://raw.githubusercontent.com/jabine9966/sol-perp-quant-report/"
    "d73d90b66c7977f9c5627367350edb0d52bd6088/data/SOLUSDT_1h.csv"
)


@dataclass(frozen=True)
class CandidateResult:
    params: Dict[str, Any]
    metrics: Dict[str, float]


def _load_csv_from_url(url: str, timeout_seconds: int = 30) -> bytes:
    if requests is None:
        raise RuntimeError("requests no está disponible para descargar CSV")
    r = requests.get(url, timeout=timeout_seconds)
    r.raise_for_status()
    return r.content


def load_ohlcv_dataframe_from_csv_url(url: str) -> pd.DataFrame:
    """
    Carga un CSV OHLCV con columnas: timestamp, open, high, low, close, volume.
    timestamp puede venir en ms unix o en string datetime.
    """
    content = _load_csv_from_url(url)
    df = pd.read_csv(io.BytesIO(content))

    # Normalizar columnas
    if "timestamp" not in df.columns:
        raise ValueError("CSV debe incluir columna 'timestamp'")

    if df["timestamp"].dtype == "object":
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    else:
        # asumir ms unix
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True, errors="coerce")

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            raise ValueError(f"CSV debe incluir columna '{col}'")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def _profit_factor_from_trades(trades: List[Dict[str, Any]]) -> float:
    gross_profit = sum(t.get("pnl", 0.0) for t in trades if t.get("pnl", 0.0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0.0) for t in trades if t.get("pnl", 0.0) < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _score(metrics: Dict[str, float]) -> float:
    """
    Score multiobjetivo simple:
    - prioriza ROI (pnl_percent)
    - y win_rate
    - penaliza drawdown
    """
    roi = metrics.get("total_pnl_percent", 0.0)
    win_rate = metrics.get("win_rate_percent", 0.0)
    dd = metrics.get("max_drawdown_percent_abs", 0.0)
    pf = metrics.get("profit_factor", 0.0)
    # peso win_rate moderado; drawdown penaliza fuerte; profit_factor como tie-break
    return (roi * 1.0) + (win_rate * 0.15) + (math.log1p(pf) * 2.0) - (dd * 0.8)


def _make_strategy(strategy_key: str, params: Dict[str, Any]):
    if strategy_key == "basica":
        return UTBotPSARStrategy(**params)
    if strategy_key == "conservadora":
        return UTBotPSARConservativeStrategy(**params)
    if strategy_key == "optimizada":
        return UTBotPSAROptimizedStrategy(**params)
    raise ValueError(f"strategy_key inválida: {strategy_key}")


def _param_space(strategy_key: str) -> Dict[str, Any]:
    # rangos razonables para 1h cripto
    base = {
        "sensitivity": [1, 2, 3, 4],
        "atr_period": [7, 10, 14, 21],
        "use_heikin_ashi": [False, True],
        "risk_percent": [0.5, 1.0, 1.5, 2.0],
        "tp_atr_multiplier": [1.5, 2.0, 2.5, 3.0],
        "sl_atr_multiplier": [1.0, 1.5, 2.0],
        "psar_start": [0.01, 0.02, 0.03],
        "psar_increment": [0.01, 0.02, 0.03],
        "psar_max": [0.1, 0.2, 0.3],
    }

    if strategy_key == "conservadora":
        base.update(
            {
                "min_atr_filter": [True, False],
                "trend_filter": [True, False],
            }
        )
    return base


def _sample_params(rng: random.Random, space: Dict[str, List[Any]]) -> Dict[str, Any]:
    return {k: rng.choice(v) for k, v in space.items()}


def evaluate_candidate(
    symbol: str,
    data: pd.DataFrame,
    strategy_key: str,
    params: Dict[str, Any],
    initial_capital: float,
    commission_percent: float,
) -> CandidateResult:
    strategy = _make_strategy(strategy_key, params)
    backtester = AdvancedBacktester(initial_capital=initial_capital, commission=commission_percent)
    result = backtester.run(strategy, data, symbol)

    total_trades = float(result.get("total_trades", 0) or 0)
    win_rate = float(result.get("win_rate", 0) or 0) * 100.0
    total_pnl = float(result.get("total_pnl", 0) or 0)
    max_dd_raw = float(result.get("max_drawdown", 0) or 0)
    trades = result.get("trades", []) or []
    profit_factor = _profit_factor_from_trades(trades)

    metrics = {
        "total_trades": total_trades,
        "win_rate_percent": win_rate,
        "total_pnl": total_pnl,
        "total_pnl_percent": (total_pnl / initial_capital) * 100.0 if initial_capital else 0.0,
        "max_drawdown_raw": max_dd_raw,
        "max_drawdown_abs": abs(max_dd_raw),
        "max_drawdown_percent_abs": (abs(max_dd_raw) / initial_capital) * 100.0 if initial_capital else 0.0,
        "profit_factor": float(profit_factor),
    }
    metrics["score"] = _score(metrics)
    return CandidateResult(params=params, metrics=metrics)


def random_search(
    *,
    symbol: str,
    strategy_key: str,
    df_ohlcv: pd.DataFrame,
    iters: int,
    seed: int,
    initial_capital: float,
    commission_percent: float,
    top_n: int,
) -> List[CandidateResult]:
    rng = random.Random(seed)
    space = _param_space(strategy_key)

    seen: set[Tuple[Tuple[str, Any], ...]] = set()
    best: List[CandidateResult] = []

    for _ in range(max(1, iters)):
        params = _sample_params(rng, space)
        key = tuple(sorted(params.items(), key=lambda x: x[0]))
        if key in seen:
            continue
        seen.add(key)

        cand = evaluate_candidate(
            symbol=symbol,
            data=df_ohlcv,
            strategy_key=strategy_key,
            params=params,
            initial_capital=initial_capital,
            commission_percent=commission_percent,
        )
        best.append(cand)
        best.sort(key=lambda c: c.metrics.get("score", 0.0), reverse=True)
        best = best[: max(1, top_n)]

    return best


def save_optimization_results(
    *,
    out_path: Path,
    symbol: str,
    strategy_key: str,
    results: List[CandidateResult],
    meta: Dict[str, Any],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "strategy": strategy_key,
        "meta": meta,
        "top": [
            {"params": r.params, "metrics": r.metrics}
            for r in results
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
