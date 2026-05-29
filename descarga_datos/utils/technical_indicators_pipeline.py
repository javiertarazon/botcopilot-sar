"""
Pipeline compartido de indicadores técnicos.

Este módulo centraliza el cálculo de indicadores que son necesarios para:
- Estrategias (UT Bot + PSAR)
- Backtesting
- Paper trading / Live trading

La intención es evitar divergencias entre el cálculo usado en backtesting y en trading.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_sar(df: pd.DataFrame) -> pd.Series:
    """Calcula Parabolic SAR simplificado (misma lógica que el downloader)."""
    length = len(df)
    sar = np.zeros(length, dtype=float)
    if length == 0:
        return pd.Series([], dtype=float, index=df.index)

    high = df["high"].to_numpy(dtype=float, copy=False)
    low = df["low"].to_numpy(dtype=float, copy=False)

    sar[0] = low[0]

    acceleration = 0.02
    max_acceleration = 0.2

    trend = 1  # 1 = uptrend, -1 = downtrend
    extreme_point = high[0]
    acceleration_factor = acceleration

    for i in range(1, length):
        sar[i] = sar[i - 1] + acceleration_factor * (extreme_point - sar[i - 1])

        if trend == 1:
            if low[i] <= sar[i]:
                trend = -1
                sar[i] = extreme_point
                extreme_point = low[i]
                acceleration_factor = acceleration
            else:
                if high[i] > extreme_point:
                    extreme_point = high[i]
                    acceleration_factor = min(acceleration_factor + acceleration, max_acceleration)
                sar[i] = min(sar[i], low[i - 1], low[i])
        else:
            if high[i] >= sar[i]:
                trend = 1
                sar[i] = extreme_point
                extreme_point = high[i]
                acceleration_factor = acceleration
            else:
                if low[i] < extreme_point:
                    extreme_point = low[i]
                    acceleration_factor = min(acceleration_factor + acceleration, max_acceleration)
                sar[i] = max(sar[i], high[i - 1], high[i])

    return pd.Series(sar, index=df.index, dtype=float)


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula indicadores técnicos (ATR/ADX/SAR/RSI/MACD/EMAs/Bollinger).

    Nota: Este cálculo mantiene valores "raw" (no normaliza SAR),
    ya que las estrategias comparan precio contra niveles en la misma escala.
    """
    result_df = df.copy()

    # ATR
    high_low = result_df["high"] - result_df["low"]
    high_close = np.abs(result_df["high"] - result_df["close"].shift(1))
    low_close = np.abs(result_df["low"] - result_df["close"].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    result_df["atr"] = tr.ewm(span=14, adjust=False).mean()

    # ADX
    high_diff = result_df["high"].diff()
    low_diff = result_df["low"].diff()
    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    atr_val = result_df["atr"]
    plus_di = 100 * (pd.Series(plus_dm, index=result_df.index).ewm(span=14, adjust=False).mean() / atr_val)
    minus_di = 100 * (pd.Series(minus_dm, index=result_df.index).ewm(span=14, adjust=False).mean() / atr_val)
    dx = 100 * np.abs((plus_di - minus_di) / ((plus_di + minus_di) + 1e-9))
    result_df["adx"] = dx.ewm(span=14, adjust=False).mean()

    # SAR
    result_df["sar"] = calculate_sar(result_df)

    # RSI
    delta = result_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    result_df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema_12 = result_df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = result_df["close"].ewm(span=26, adjust=False).mean()
    result_df["macd"] = ema_12 - ema_26
    result_df["macd_signal"] = result_df["macd"].ewm(span=9, adjust=False).mean()

    # EMAs
    result_df["ema_10"] = result_df["close"].ewm(span=10, adjust=False).mean()
    result_df["ema_20"] = result_df["close"].ewm(span=20, adjust=False).mean()
    result_df["ema_200"] = result_df["close"].ewm(span=200, adjust=False).mean()

    # Bollinger Bands
    sma_20 = result_df["close"].rolling(window=20).mean()
    std_20 = result_df["close"].rolling(window=20).std()
    result_df["bb_upper"] = sma_20 + (std_20 * 2)
    result_df["bb_lower"] = sma_20 - (std_20 * 2)

    return result_df.fillna(0)

