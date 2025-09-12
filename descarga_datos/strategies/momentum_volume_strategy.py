"""
ALTERNATIVA 4: ESTRATEGIA DE MOMENTUM AVANZADO CON ANÁLISIS DE VOLUMEN
====================================================================

Estrategia que combina momentum institucional con análisis de volumen avanzado
y señales UT Bot para identificar movimientos de alta calidad.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy.stats import linregress
import warnings
warnings.filterwarnings('ignore')

@dataclass
class MomentumVolumeConfig:
    """Configuración para estrategia de momentum con volumen"""
    # Parámetros de momentum
    momentum_periods: List[int] = None  # [10, 20, 50, 100]
    momentum_weights: List[float] = None  # Pesos para cada período

    # Parámetros de volumen
    volume_ma_period: int = 20
    volume_surge_threshold: float = 1.5  # 50% por encima de la media
    relative_volume_threshold: float = 1.2

    # Parámetros UT Bot
    ut_bot_sensitivity: int = 2
    ut_bot_atr_period: int = 14
    use_ut_bot_confirmation: bool = True

    # Filtros adicionales
    min_price: float = 0.000001  # Evitar micro-cap
    max_price: float = 1000000  # Evitar precios extremos
    min_volume: int = 1000  # Volumen mínimo diario

    # Gestión de riesgo
    risk_per_trade: float = 0.015  # 1.5% por trade
    max_positions: int = 5
    max_allocation_per_position: float = 0.25  # 25% por posición

    # Parámetros de salida
    profit_target_multiplier: float = 2.5
    stop_loss_multiplier: float = 1.5
    trailing_stop_activation: float = 0.02  # 2% para activar trailing

class MomentumVolumeStrategy:
    """
    Estrategia de Momentum Avanzado con Análisis de Volumen

    Características:
    - Momentum compuesto con múltiples períodos
    - Análisis de volumen institucional
    - Detección de acumulación/distribución
    - Confirmación con UT Bot
    - Gestión de riesgo adaptativa
    """

    def __init__(self, config: MomentumVolumeConfig = None):
        self.config = config or MomentumVolumeConfig()

        if self.config.momentum_periods is None:
            self.config.momentum_periods = [10, 20, 50, 100]

        if self.config.momentum_weights is None:
            self.config.momentum_weights = [0.4, 0.3, 0.2, 0.1]  # Más peso a momentum corto

        # Estado de la estrategia
        self.active_positions = {}
        self.performance_history = []
        self.momentum_cache = {}

    def calculate_momentum_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula score de momentum compuesto
        """
        momentum_scores = pd.DataFrame(index=df.index)

        for period, weight in zip(self.config.momentum_periods, self.config.momentum_weights):
            # Momentum simple
            momentum = (df['close'] - df['close'].shift(period)) / df['close'].shift(period)

            # Momentum suavizado con EMA
            momentum_smooth = momentum.ewm(span=period//2).mean()

            # Normalizar momentum (-1 a 1)
            momentum_norm = momentum_smooth / (momentum_smooth.abs().rolling(period).mean() + 1e-8)

            momentum_scores[f'momentum_{period}'] = momentum_norm * weight

        # Score compuesto
        momentum_score = momentum_scores.sum(axis=1)

        # Normalizar score final
        momentum_score = momentum_score / momentum_score.abs().rolling(20).mean()

        return momentum_score.clip(-2, 2)  # Limitar entre -2 y 2

    def calculate_volume_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula score de volumen avanzado
        """
        # Media móvil de volumen
        volume_ma = df['volume'].rolling(self.config.volume_ma_period).mean()

        # Volume ratio
        volume_ratio = df['volume'] / volume_ma

        # Relative volume (comparado con período más largo)
        volume_ma_long = df['volume'].rolling(50).mean()
        relative_volume = volume_ma / volume_ma_long

        # Volume surge (picos de volumen)
        volume_surge = (df['volume'] / volume_ma).clip(upper=3)  # Máximo 3x

        # Price-Volume Trend (PVT)
        price_change = df['close'].pct_change()
        pvt = (price_change * df['volume']).cumsum()

        # Normalizar PVT
        pvt_norm = (pvt - pvt.rolling(20).mean()) / pvt.rolling(20).std()

        # Combinar indicadores de volumen
        volume_score = (
            0.3 * volume_ratio.clip(0, 3) +  # Ratio de volumen
            0.3 * relative_volume.clip(0, 3) +  # Volumen relativo
            0.2 * volume_surge +  # Picos de volumen
            0.2 * pvt_norm.clip(-2, 2)  # Price-Volume Trend
        )

        return volume_score

    def detect_institutional_activity(self, df: pd.DataFrame) -> pd.Series:
        """
        Detecta actividad institucional basada en patrones de volumen y precio
        """
        # Large Volume Days
        volume_ma = df['volume'].rolling(20).mean()
        large_volume = (df['volume'] > volume_ma * 1.5).astype(int)

        # Price consolidation followed by breakout
        high_20 = df['high'].rolling(20).max()
        low_20 = df['low'].rolling(20).min()
        consolidation = ((high_20 - low_20) / df['close']).rolling(10).mean()

        # Breakout detection
        breakout_up = (df['close'] > high_20.shift(1)) & (df['volume'] > volume_ma * 1.2)
        breakout_down = (df['close'] < low_20.shift(1)) & (df['volume'] > volume_ma * 1.2)

        # Accumulation/Distribution Index (ADI)
        price_move = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-8)
        adi = (price_move * df['volume']).cumsum()

        # Normalizar ADI
        adi_norm = (adi - adi.rolling(20).mean()) / adi.rolling(20).std()

        # Score de actividad institucional
        institutional_score = (
            0.3 * large_volume +
            0.2 * breakout_up.astype(int) +
            0.2 * breakout_down.astype(int) +
            0.3 * adi_norm.clip(-2, 2)
        )

        return institutional_score

    def calculate_ut_bot_confirmation(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula confirmación de UT Bot para timing
        """
        df = df.copy()

        # Calcular indicadores UT Bot
        df['atr'] = self.calculate_atr(df, self.config.ut_bot_atr_period)
        df['n_loss'] = self.config.ut_bot_sensitivity * df['atr']

        # Trailing stop
        df['trailing_stop'] = self.calculate_trailing_stop(df)

        # Señales
        df['ema_val'] = df['close']
        df['above'] = (df['ema_val'] > df['trailing_stop']) & (df['ema_val'].shift(1) <= df['trailing_stop'].shift(1))
        df['below'] = (df['ema_val'] < df['trailing_stop']) & (df['ema_val'].shift(1) >= df['trailing_stop'].shift(1))

        df['ut_bot_bullish'] = (df['close'] > df['trailing_stop']) & df['above']
        df['ut_bot_bearish'] = (df['close'] < df['trailing_stop']) & df['below']

        return df['ut_bot_bullish'].astype(int) - df['ut_bot_bearish'].astype(int)

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

    def calculate_trailing_stop(self, df: pd.DataFrame) -> pd.Series:
        """Calcula trailing stop UT Bot"""
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

    def calculate_composite_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula señal compuesta combinando momentum, volumen y UT Bot
        """
        df = df.copy()

        # Calcular componentes
        df['momentum_score'] = self.calculate_momentum_score(df)
        df['volume_score'] = self.calculate_volume_score(df)
        df['institutional_score'] = self.detect_institutional_activity(df)

        if self.config.use_ut_bot_confirmation:
            df['ut_bot_signal'] = self.calculate_ut_bot_confirmation(df)
        else:
            df['ut_bot_signal'] = 0

        # Filtros básicos de calidad
        price_filter = (df['close'] >= self.config.min_price) & (df['close'] <= self.config.max_price)
        volume_filter = df['volume'] >= self.config.min_volume

        # Señal compuesta
        composite_score = (
            0.4 * df['momentum_score'] +
            0.3 * df['volume_score'] +
            0.2 * df['institutional_score'] +
            0.1 * df['ut_bot_signal']
        )

        # Aplicar filtros
        df['composite_signal'] = composite_score * price_filter * volume_filter

        # Generar señales de entrada/salida
        signal_threshold = df['composite_signal'].rolling(20).mean() + df['composite_signal'].rolling(20).std()

        df['buy_signal'] = (
            (df['composite_signal'] > signal_threshold) &
            (df['composite_signal'] > 0.5) &  # Umbral mínimo
            (df['momentum_score'] > 0) &      # Momentum positivo
            (df['volume_score'] > 1.0)        # Volumen suficiente
        )

        df['sell_signal'] = (
            (df['composite_signal'] < -signal_threshold) &
            (df['composite_signal'] < -0.5) & # Umbral mínimo
            (df['momentum_score'] < 0) &      # Momentum negativo
            (df['volume_score'] > 1.0)        # Volumen suficiente
        )

        return df

    def calculate_position_size(self, capital: float, entry_price: float,
                              volatility: float, momentum_strength: float) -> float:
        """
        Calcula tamaño de posición basado en volatilidad y momentum
        """
        # Riesgo base por trade
        risk_amount = capital * self.config.risk_per_trade

        # Ajuste por volatilidad (más vol = menos posición)
        volatility_adjustment = 1 / (1 + volatility)

        # Ajuste por momentum (más fuerte = más posición)
        momentum_adjustment = 1 + abs(momentum_strength) * 0.5

        # Calcular posición
        position_value = risk_amount * volatility_adjustment * momentum_adjustment

        # Limitar por porcentaje máximo de capital
        max_position_value = capital * self.config.max_allocation_per_position
        position_value = min(position_value, max_position_value)

        # Convertir a unidades
        units = position_value / entry_price

        return units

    def calculate_dynamic_stops(self, df: pd.DataFrame, entry_price: float,
                              position_type: str) -> Tuple[float, float]:
        """
        Calcula stops dinámicos basados en volatilidad y momentum
        """
        current_atr = df['atr'].iloc[-1]
        current_momentum = df['momentum_score'].iloc[-1]

        # Stop loss base
        if position_type == 'long':
            base_sl = entry_price - (current_atr * self.config.stop_loss_multiplier)
            base_tp = entry_price + (current_atr * self.config.profit_target_multiplier)
        else:
            base_sl = entry_price + (current_atr * self.config.stop_loss_multiplier)
            base_tp = entry_price - (current_atr * self.config.profit_target_multiplier)

        # Ajustar por momentum
        momentum_factor = 1 + abs(current_momentum) * 0.3

        # Calcular stops finales
        if position_type == 'long':
            stop_loss = entry_price - (current_atr * self.config.stop_loss_multiplier * momentum_factor)
            take_profit = entry_price + (current_atr * self.config.profit_target_multiplier * momentum_factor)
        else:
            stop_loss = entry_price + (current_atr * self.config.stop_loss_multiplier * momentum_factor)
            take_profit = entry_price - (current_atr * self.config.profit_target_multiplier * momentum_factor)

        return stop_loss, take_profit

    def run_backtest(self, data: pd.DataFrame, symbol: str) -> Dict:
        """
        Ejecuta backtest de la estrategia de momentum con volumen
        """
        # Calcular señales
        df = self.calculate_composite_signal(data)

        capital = 10000.0
        position = 0
        trades = []
        entry_price = 0
        stop_loss = 0
        take_profit = 0

        for i in range(50, len(df)):  # Empezar después del período de calentamiento
            current_row = df.iloc[i]
            current_price = current_row['close']

            # Verificar señales de entrada
            if position == 0:
                if current_row['buy_signal']:
                    # Entrar en posición long
                    position = 1
                    entry_price = current_price

                    # Calcular stops dinámicos
                    stop_loss, take_profit = self.calculate_dynamic_stops(
                        df.iloc[max(0, i-20):i+1], entry_price, 'long'
                    )

                    # Calcular tamaño de posición
                    volatility = df['atr'].iloc[i] / current_price  # Volatilidad relativa
                    momentum_strength = current_row['momentum_score']

                    position_size = self.calculate_position_size(
                        capital, entry_price, volatility, momentum_strength
                    )

                    # Verificar límites
                    if len(self.active_positions) < self.config.max_positions:
                        self.active_positions[symbol] = {
                            'type': 'long',
                            'entry_price': entry_price,
                            'position_size': position_size,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_date': df.index[i],
                            'momentum_at_entry': momentum_strength,
                            'volume_at_entry': current_row['volume_score']
                        }

                elif current_row['sell_signal']:
                    # Entrar en posición short
                    position = -1
                    entry_price = current_price

                    # Calcular stops dinámicos
                    stop_loss, take_profit = self.calculate_dynamic_stops(
                        df.iloc[max(0, i-20):i+1], entry_price, 'short'
                    )

                    # Calcular tamaño de posición
                    volatility = df['atr'].iloc[i] / current_price
                    momentum_strength = current_row['momentum_score']

                    position_size = self.calculate_position_size(
                        capital, entry_price, volatility, momentum_strength
                    )

                    # Verificar límites
                    if len(self.active_positions) < self.config.max_positions:
                        self.active_positions[symbol] = {
                            'type': 'short',
                            'entry_price': entry_price,
                            'position_size': position_size,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_date': df.index[i],
                            'momentum_at_entry': momentum_strength,
                            'volume_at_entry': current_row['volume_score']
                        }

            # Verificar condiciones de salida
            elif position != 0 and symbol in self.active_positions:
                pos_info = self.active_positions[symbol]

                exit_condition = False
                exit_price = current_price

                if position == 1:  # Long position
                    if current_price >= pos_info['take_profit'] or current_price <= pos_info['stop_loss']:
                        exit_condition = True
                else:  # Short position
                    if current_price <= pos_info['take_profit'] or current_price >= pos_info['stop_loss']:
                        exit_condition = True

                if exit_condition:
                    # Calcular P&L
                    if position == 1:
                        pnl = (exit_price - entry_price) * pos_info['position_size']
                    else:
                        pnl = (entry_price - exit_price) * pos_info['position_size']

                    capital += pnl

                    # Registrar trade
                    trades.append({
                        'entry_date': pos_info['entry_date'],
                        'exit_date': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'position_type': 'long' if position == 1 else 'short',
                        'pnl': pnl,
                        'momentum_at_entry': pos_info['momentum_at_entry'],
                        'volume_at_entry': pos_info['volume_at_entry'],
                        'holding_period': (df.index[i] - pos_info['entry_date']).days
                    })

                    # Limpiar posición
                    del self.active_positions[symbol]
                    position = 0

        # Calcular métricas finales
        if not trades:
            return {'error': 'No se generaron trades'}

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
            'avg_holding_period': np.mean([t['holding_period'] for t in trades]),
            'final_capital': capital,
            'total_return': (capital - 10000.0) / 10000.0 * 100,
            'trades': trades
        }
