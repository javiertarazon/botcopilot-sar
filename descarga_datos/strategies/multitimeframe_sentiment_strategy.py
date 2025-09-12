"""
ALTERNATIVA 2: ESTRATEGIA MULTI-TIMEFRAME CON ANÁLISIS DE SENTIMIENTO
====================================================================

Estrategia que combina análisis multi-timeframe con indicadores de sentimiento
del mercado para mejorar la calidad de las señales.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
import json

@dataclass
class MultiTimeframeConfig:
    """Configuración para estrategia multi-timeframe"""
    base_timeframe: str = "1h"
    higher_timeframes: List[str] = None  # ["4h", "1d"]
    lower_timeframe: str = "15m"  # Para confirmación de entrada

    # Pesos para diferentes timeframes
    base_weight: float = 0.5
    higher_weight: float = 0.3
    lower_weight: float = 0.2

    # Parámetros de sentimiento
    use_sentiment: bool = True
    sentiment_threshold: float = 0.6  # 60% umbral para señales
    news_impact_window: int = 24  # Horas que afecta una noticia

    # Parámetros UT Bot adaptados
    sensitivity: int = 2
    atr_period: int = 14
    risk_percent: float = 1.2

class SentimentMultiTimeframeStrategy:
    """
    Estrategia UT Bot + PSAR Multi-Timeframe con Análisis de Sentimiento

    Características:
    - Análisis multi-timeframe para mejor timing
    - Integración de sentimiento del mercado
    - Confirmación en timeframe inferior
    - Filtros de momentum alineado
    """

    def __init__(self, config: MultiTimeframeConfig = None):
        self.config = config or MultiTimeframeConfig()
        if self.config.higher_timeframes is None:
            self.config.higher_timeframes = ["4h", "1d"]

        # Almacenamiento de datos multi-timeframe
        self.timeframe_data = {}
        self.sentiment_data = {}

        # Estado de la estrategia
        self.current_sentiment = 0.5  # Neutral
        self.last_news_time = None

    def add_timeframe_data(self, timeframe: str, data: pd.DataFrame):
        """Agrega datos de un timeframe específico"""
        self.timeframe_data[timeframe] = data.copy()

        # Calcular indicadores para este timeframe
        self._calculate_timeframe_indicators(timeframe)

    def _calculate_timeframe_indicators(self, timeframe: str):
        """Calcula indicadores para un timeframe específico"""
        df = self.timeframe_data[timeframe]

        # Calcular ATR
        df['atr'] = self.calculate_atr(df, self.config.atr_period)

        # Calcular PSAR
        df['sar'] = self.calculate_psar(df)

        # Calcular trailing stop UT Bot
        df['n_loss'] = self.config.sensitivity * df['atr']
        df['trailing_stop'] = self.calculate_trailing_stop(df)

        # Calcular señales básicas
        df['ema_val'] = df['close']
        df['above'] = (df['ema_val'] > df['trailing_stop']) & (df['ema_val'].shift(1) <= df['trailing_stop'].shift(1))
        df['below'] = (df['ema_val'] < df['trailing_stop']) & (df['ema_val'].shift(1) >= df['trailing_stop'].shift(1))

        # Señales por dirección
        df['bullish_signal'] = (df['close'] > df['trailing_stop']) & df['above']
        df['bearish_signal'] = (df['close'] < df['trailing_stop']) & df['below']

        self.timeframe_data[timeframe] = df

    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula ATR"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def calculate_psar(self, df: pd.DataFrame) -> pd.Series:
        """Calcula Parabolic SAR"""
        high = df['high'].values
        low = df['low'].values

        psar = np.zeros(len(df))
        psar[0] = low[0]

        acceleration = 0.02
        max_acceleration = 0.2

        trend = 1  # 1 = uptrend, -1 = downtrend
        extreme_point = high[0]

        for i in range(1, len(df)):
            psar[i] = psar[i-1] + acceleration * (extreme_point - psar[i-1])

            if trend == 1:  # Uptrend
                if low[i] <= psar[i]:
                    trend = -1
                    psar[i] = extreme_point
                    extreme_point = low[i]
                    acceleration = 0.02
                else:
                    if high[i] > extreme_point:
                        extreme_point = high[i]
                        acceleration = min(acceleration + 0.02, max_acceleration)
            else:  # Downtrend
                if high[i] >= psar[i]:
                    trend = 1
                    psar[i] = extreme_point
                    extreme_point = high[i]
                    acceleration = 0.02
                else:
                    if low[i] < extreme_point:
                        extreme_point = low[i]
                        acceleration = min(acceleration + 0.02, max_acceleration)

        return pd.Series(psar, index=df.index)

    def calculate_trailing_stop(self, df: pd.DataFrame) -> pd.Series:
        """Calcula trailing stop estilo UT Bot"""
        trailing_stop = pd.Series(index=df.index, dtype=float)

        for i in range(len(df)):
            price = df['close'].iloc[i]
            n_loss = df['n_loss'].iloc[i]

            if i == 0:
                trailing_stop.iloc[i] = price - n_loss
                continue

            prev_stop = trailing_stop.iloc[i-1]

            if price > prev_stop:
                trailing_stop.iloc[i] = max(prev_stop, price - n_loss)
            else:
                trailing_stop.iloc[i] = price + n_loss

        return trailing_stop

    def get_sentiment_data(self, symbol: str) -> float:
        """
        Obtiene datos de sentimiento del mercado
        En producción, esto se conectaría a APIs de noticias y redes sociales
        """
        try:
            # Simulación de análisis de sentimiento
            # En producción: conectar con APIs como Alpha Vantage, NewsAPI, Twitter API, etc.

            # Simular sentimiento basado en volatilidad reciente y momentum
            if symbol in self.timeframe_data:
                df = self.timeframe_data[symbol]

                if len(df) > 50:
                    # Calcular indicadores de sentimiento
                    recent_returns = df['close'].pct_change().tail(20)
                    volatility = recent_returns.std()

                    # RSI como indicador de momentum
                    rsi = self.calculate_rsi(df['close'].tail(50))

                    # Combinar indicadores para sentimiento
                    momentum_score = (rsi.iloc[-1] - 50) / 50  # -1 a 1
                    volatility_score = min(volatility * 10, 1)  # 0 a 1

                    sentiment = 0.5 + (momentum_score * 0.3) + (volatility_score * 0.2)
                    sentiment = max(0, min(1, sentiment))  # Clamp entre 0 y 1

                    return sentiment

            return 0.5  # Neutral por defecto

        except Exception as e:
            print(f"Error obteniendo sentimiento: {e}")
            return 0.5

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_multitimeframe_signal(self, symbol: str, current_time: pd.Timestamp) -> Dict:
        """
        Calcula señal combinando múltiples timeframes
        """
        signal_data = {
            'bullish_score': 0.0,
            'bearish_score': 0.0,
            'confidence': 0.0,
            'recommended_action': 'HOLD'
        }

        if self.config.base_timeframe not in self.timeframe_data:
            return signal_data

        base_df = self.timeframe_data[self.config.base_timeframe]

        # Encontrar el índice más cercano al tiempo actual
        try:
            current_idx = base_df.index.get_loc(current_time, method='nearest')
            current_row = base_df.iloc[current_idx]
        except:
            return signal_data

        # Evaluar timeframe base
        base_bullish = current_row['bullish_signal']
        base_bearish = current_row['bearish_signal']

        # Evaluar timeframes superiores
        higher_bullish = 0
        higher_bearish = 0
        higher_count = 0

        for tf in self.config.higher_timeframes:
            if tf in self.timeframe_data:
                higher_df = self.timeframe_data[tf]
                try:
                    higher_idx = higher_df.index.get_loc(current_time, method='nearest')
                    higher_row = higher_df.iloc[higher_idx]

                    if higher_row['bullish_signal']:
                        higher_bullish += 1
                    if higher_row['bearish_signal']:
                        higher_bearish += 1
                    higher_count += 1
                except:
                    continue

        # Evaluar timeframe inferior (para timing de entrada)
        lower_confirmation = False
        if self.config.lower_timeframe in self.timeframe_data:
            lower_df = self.timeframe_data[self.config.lower_timeframe]
            try:
                lower_idx = lower_df.index.get_loc(current_time, method='nearest')
                # Revisar últimas N velas del timeframe inferior
                recent_lower = lower_df.iloc[max(0, lower_idx-3):lower_idx+1]

                # Confirmación si hay momentum en la dirección correcta
                if base_bullish and (recent_lower['close'] > recent_lower['close'].shift(1)).sum() >= 2:
                    lower_confirmation = True
                elif base_bearish and (recent_lower['close'] < recent_lower['close'].shift(1)).sum() >= 2:
                    lower_confirmation = True
            except:
                pass

        # Calcular scores ponderados
        base_score = self.config.base_weight
        higher_score = self.config.higher_weight * (higher_bullish - higher_bearish) / max(higher_count, 1)
        lower_score = self.config.lower_weight if lower_confirmation else 0

        total_bullish = (base_score if base_bullish else 0) + max(0, higher_score) + (lower_score if base_bullish else 0)
        total_bearish = (base_score if base_bearish else 0) + max(0, -higher_score) + (lower_score if base_bearish else 0)

        # Obtener sentimiento del mercado
        sentiment = self.get_sentiment_data(symbol)

        # Aplicar filtro de sentimiento
        if self.config.use_sentiment:
            if sentiment > self.config.sentiment_threshold:
                total_bullish *= 1.2  # Boost señales bullish en sentimiento positivo
            elif sentiment < (1 - self.config.sentiment_threshold):
                total_bearish *= 1.2  # Boost señales bearish en sentimiento negativo

        # Determinar acción recomendada
        signal_data['bullish_score'] = total_bullish
        signal_data['bearish_score'] = total_bearish
        signal_data['confidence'] = max(total_bullish, total_bearish)

        if total_bullish > total_bearish and total_bullish > 0.5:
            signal_data['recommended_action'] = 'BUY'
        elif total_bearish > total_bullish and total_bearish > 0.5:
            signal_data['recommended_action'] = 'SELL'

        return signal_data

    def run_backtest(self, data: pd.DataFrame, symbol: str) -> Dict:
        """Ejecuta backtest multi-timeframe"""
        # Usar los datos proporcionados
        self.timeframe_data = {self.config.base_timeframe: data}
        base_df = self.timeframe_data[self.config.base_timeframe]

        capital = 10000.0
        position = 0
        trades = []

        for i in range(50, len(base_df)):  # Empezar después de período de calentamiento
            current_time = base_df.index[i]

            # Obtener señal multi-timeframe
            signal = self.calculate_multitimeframe_signal(symbol, current_time)

            current_price = base_df.iloc[i]['close']

            # Ejecutar trades basado en señales
            if signal['recommended_action'] == 'BUY' and position == 0:
                position = 1
                entry_price = current_price
                entry_time = current_time

            elif signal['recommended_action'] == 'SELL' and position == 1:
                exit_price = current_price
                pnl = (exit_price - entry_price) * (capital * self.config.risk_percent / 100) / entry_price
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'confidence': signal['confidence']
                })

                position = 0

        # Calcular métricas
        if not trades:
            return {'error': 'No trades generated'}

        winning_trades = [t for t in trades if t['pnl'] > 0]

        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'win_rate': len(winning_trades) / len(trades),
            'total_pnl': sum(t['pnl'] for t in trades),
            'avg_trade_pnl': np.mean([t['pnl'] for t in trades]),
            'avg_winning_trade': np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0,
            'avg_losing_trade': np.mean([t['pnl'] for t in trades if t['pnl'] <= 0]) if [t for t in trades if t['pnl'] <= 0] else 0,
            'largest_win': max([t['pnl'] for t in trades]),
            'largest_loss': min([t['pnl'] for t in trades]),
            'avg_confidence': np.mean([t['confidence'] for t in trades])
        }
