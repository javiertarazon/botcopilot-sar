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

try:
    import optuna  # type: ignore
except ImportError:  # pragma: no cover
    optuna = None

try:
    import ccxt  # type: ignore
except ImportError:  # pragma: no cover
    ccxt = None

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


def _max_drawdown_from_trade_pnls(trade_pnls: List[float], initial_capital: float) -> float:
    """
    Calcula max drawdown absoluto (>=0) sobre una curva de equity por-trade.
    """
    if initial_capital <= 0:
        return 0.0
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    for pnl in trade_pnls:
        equity += float(pnl)
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)


def _load_csv_from_url(url: str, timeout_seconds: int = 30) -> bytes:
    if requests is None:
        raise RuntimeError("requests no está disponible para descargar CSV")
    r = requests.get(url, timeout=timeout_seconds)
    r.raise_for_status()
    return r.content


def load_ohlcv_dataframe_from_csv(url_or_path: str) -> pd.DataFrame:
    """
    Carga un CSV OHLCV con columnas: timestamp, open, high, low, close, volume.
    timestamp puede venir en ms unix o en string datetime.
    """
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        content = _load_csv_from_url(url_or_path)
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_csv(url_or_path)

    # Normalizar nombres de columnas (case-insensitive) y soportar formatos comunes:
    # - timestamp, open, high, low, close, volume (ms unix o datetime)
    # - Datetime, Open, High, Low, Close, Volume, Turnover (Bybit dumps)
    colmap = {c.lower(): c for c in df.columns}

    ts_col = None
    if "timestamp" in colmap:
        ts_col = colmap["timestamp"]
    elif "datetime" in colmap:
        ts_col = colmap["datetime"]
    elif "date" in colmap:
        ts_col = colmap["date"]
    elif "time" in colmap:
        ts_col = colmap["time"]

    if ts_col is None:
        raise ValueError("CSV debe incluir columna temporal ('timestamp' o 'Datetime')")

    def _pick(required: str) -> str:
        key = required.lower()
        if key in colmap:
            return colmap[key]
        raise ValueError(f"CSV debe incluir columna '{required}'")

    open_col = _pick("open")
    high_col = _pick("high")
    low_col = _pick("low")
    close_col = _pick("close")
    volume_col = _pick("volume")

    ts_series = df[ts_col]
    if ts_series.dtype == "object":
        df["timestamp"] = pd.to_datetime(ts_series, utc=True, errors="coerce")
    else:
        # asumir ms unix
        df["timestamp"] = pd.to_datetime(ts_series, unit="ms", utc=True, errors="coerce")

    df["open"] = pd.to_numeric(df[open_col], errors="coerce")
    df["high"] = pd.to_numeric(df[high_col], errors="coerce")
    df["low"] = pd.to_numeric(df[low_col], errors="coerce")
    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
    df["volume"] = pd.to_numeric(df[volume_col], errors="coerce")

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def download_ohlcv_dataframe_via_ccxt(
    *,
    exchange_name: str,
    symbol: str,
    timeframe: str,
    start_ts: pd.Timestamp,
    end_ts: Optional[pd.Timestamp] = None,
    limit_per_request: int = 1000,
) -> pd.DataFrame:
    """
    Descarga OHLCV (timestamp, open, high, low, close, volume) via CCXT paginando con `since`.
    No requiere credenciales para mercados spot públicos.
    """
    if ccxt is None:
        raise RuntimeError("ccxt no está instalado. Instala `ccxt` para descargar OHLCV vía exchange.")

    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts is not None and end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")

    exchange_cls = getattr(ccxt, exchange_name, None)
    if exchange_cls is None:
        raise ValueError(f"Exchange CCXT no soportado: {exchange_name}")

    exchange = exchange_cls({"enableRateLimit": True})
    try:
        since_ms = int(start_ts.timestamp() * 1000)
        end_ms = int(end_ts.timestamp() * 1000) if end_ts is not None else None

        all_rows: list[list[float]] = []
        last_ts: Optional[int] = None

        while True:
            batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=int(limit_per_request))
            if not batch:
                break

            # Evitar loops si el exchange repite el último candle
            if last_ts is not None and int(batch[-1][0]) == last_ts:
                break
            last_ts = int(batch[-1][0])

            for row in batch:
                ts = int(row[0])
                if end_ms is not None and ts > end_ms:
                    break
                all_rows.append([float(x) for x in row[:6]])

            if end_ms is not None and int(batch[-1][0]) >= end_ms:
                break

            # Avanzar `since` al siguiente ms para evitar duplicados
            since_ms = int(batch[-1][0]) + 1

        if not all_rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(all_rows, columns=["timestamp_ms", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp_ms"].astype("int64"), unit="ms", utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]
    finally:
        try:
            exchange.close()
        except Exception:
            pass

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
    total_pnl_percent = float(result.get("total_pnl_percent", 0) or 0)
    max_dd_raw = float(result.get("max_drawdown", 0) or 0)
    max_dd_percent_raw = float(result.get("max_drawdown_percent", 0) or 0)
    sharpe_ratio = float(result.get("sharpe_ratio", 0) or 0)
    sortino_ratio = float(result.get("sortino_ratio", 0) or 0)
    calmar_ratio = float(result.get("calmar_ratio", 0) or 0)

    # Profit factor: si no viene, lo calculamos desde trades.
    trades = result.get("trades", []) or []
    trade_pnls = [float(t.get("pnl", 0.0) or 0.0) for t in trades if isinstance(t, dict)]
    profit_factor = float(result.get("profit_factor", 0) or 0)
    if profit_factor == 0 and trades:
        profit_factor = float(_profit_factor_from_trades(trades))

    # Max drawdown: priorizar cálculo desde equity por-trade (evita bugs en estrategias que retornan DD raw mal definido).
    max_dd_abs = 0.0
    if trade_pnls and initial_capital:
        max_dd_abs = _max_drawdown_from_trade_pnls(trade_pnls, initial_capital=float(initial_capital))
    else:
        max_dd_abs = abs(max_dd_raw)

    max_dd_percent_abs = (max_dd_abs / float(initial_capital)) * 100.0 if initial_capital else 0.0

    metrics = {
        "total_trades": total_trades,
        "win_rate_percent": win_rate,
        "total_pnl": total_pnl,
        "total_pnl_percent": total_pnl_percent if total_pnl_percent else ((total_pnl / initial_capital) * 100.0 if initial_capital else 0.0),
        "max_drawdown_raw": max_dd_raw,
        "max_drawdown_percent_raw": max_dd_percent_raw,
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_percent_abs": max_dd_percent_abs,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
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


def optuna_search(
    *,
    symbol: str,
    strategy_key: str,
    df_ohlcv: pd.DataFrame,
    n_trials: int,
    seed: int,
    initial_capital: float,
    commission_percent: float,
    top_n: int,
    max_drawdown_percent_limit: Optional[float] = None,
) -> List[CandidateResult]:
    """
    Optimización con Optuna (TPE) maximizando `score`.
    Guarda métricas completas del backtest en `trial.user_attrs["metrics"]`.
    """
    if optuna is None:
        raise RuntimeError("Optuna no está instalado. Instala `optuna` para usar optuna_search.")

    space = _param_space(strategy_key)

    def objective(trial) -> float:  # type: ignore[no-untyped-def]
        params: Dict[str, Any] = {}
        for key, values in space.items():
            params[key] = trial.suggest_categorical(key, values)

        cand = evaluate_candidate(
            symbol=symbol,
            data=df_ohlcv,
            strategy_key=strategy_key,
            params=params,
            initial_capital=initial_capital,
            commission_percent=commission_percent,
        )
        trial.set_user_attr("metrics", cand.metrics)
        dd_percent = float(cand.metrics.get("max_drawdown_percent_abs", 0.0) or 0.0)
        if max_drawdown_percent_limit is not None and dd_percent > float(max_drawdown_percent_limit):
            # Penalización fuerte para imponer restricción dura de DD.
            return -1e9
        return float(cand.metrics.get("score", 0.0))

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=max(1, int(n_trials)))

    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    completed.sort(key=lambda t: float(t.value or 0.0), reverse=True)

    results: List[CandidateResult] = []
    for t in completed[: max(1, int(top_n))]:
        metrics = t.user_attrs.get("metrics") or {}
        # Normalizar a float para JSON/sorting consistente
        metrics_float: Dict[str, float] = {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
        # Asegurar score
        if "score" not in metrics_float:
            metrics_float["score"] = float(t.value or 0.0)
        results.append(CandidateResult(params=dict(t.params), metrics=metrics_float))

    return results


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
