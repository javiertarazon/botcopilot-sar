"""
Versión ultra-conservadora de UT Bot + PSAR Strategy
Implementación literal del Pine Script con filtros adicionales de calidad
"""
import numpy as np
import pandas as pd
try:
    import talib  # type: ignore
except ImportError:  # pragma: no cover
    talib = None


def _atr_fallback(df: pd.DataFrame, period: int) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean().fillna(0)


def _ema_fallback(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean().fillna(0)


def _sar_fallback(df: pd.DataFrame, acceleration: float, maximum: float) -> pd.Series:
    # Fallback simple (misma lógica que en utils.technical_indicators_pipeline)
    from utils.technical_indicators_pipeline import calculate_sar

    return calculate_sar(df).fillna(0)

class UTBotPSARConservativeStrategy:
    """
    Implementación conservadora basada en análisis del Pine Script.
    Reduce sobretrading y mejora calidad de señales.
    """

    def __init__(self,
                 sensitivity=1,
                 atr_period=10,
                 use_heikin_ashi=False,
                 risk_percent=2.0,
                 tp_atr_multiplier=2.0,
                 sl_atr_multiplier=1.5,
                 psar_start=0.02,
                 psar_increment=0.02,
                 psar_max=0.2,
                 min_atr_filter=True,      # Filtro adicional
                 trend_filter=True):       # Filtro de tendencia fuerte
        self.sensitivity = sensitivity
        self.atr_period = atr_period
        self.use_heikin_ashi = use_heikin_ashi
        self.risk_percent = risk_percent
        self.tp_atr_multiplier = tp_atr_multiplier
        self.sl_atr_multiplier = sl_atr_multiplier
        self.psar_start = psar_start
        self.psar_increment = psar_increment
        self.psar_max = psar_max
        self.min_atr_filter = min_atr_filter
        self.trend_filter = trend_filter
        self.psar_max = psar_max
        self.min_atr_filter = min_atr_filter
        self.trend_filter = trend_filter

    def calculate_heikin_ashi(self, df):
        """Cálculo exacto de Heikin Ashi"""
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = pd.Series(0.0, index=df.index)
        ha_open.iloc[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        
        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
            
        ha_high = pd.Series([max(h, o, c) for h, o, c in zip(df['high'], ha_open, ha_close)], index=df.index)
        ha_low = pd.Series([min(l, o, c) for l, o, c in zip(df['low'], ha_open, ha_close)], index=df.index)
        
        return pd.DataFrame({
            'open': ha_open,
            'high': ha_high,
            'low': ha_low,
            'close': ha_close
        }, index=df.index)

    def calculate_crossover(self, series1, series2, df=None):
        """Crossover con filtro anti-ruido"""
        basic_cross = (series1 > series2) & (series1.shift(1) <= series2.shift(1))
        
        # Filtro anti-ruido: requiere que el crossover sea significativo
        if self.min_atr_filter and df is not None and 'atr' in df.columns:
            # El crossover debe ser mayor que 10% del ATR para ser válido
            cross_magnitude = abs(series1 - series2)
            atr_series = df['atr']
            min_magnitude = 0.1 * atr_series
            return basic_cross & (cross_magnitude > min_magnitude)
        
        return basic_cross

    def calculate_signals(self, df):
        """Implementación conservadora del Pine Script"""
        df = df.copy()
        
        # ================= CÁLCULOS PRINCIPALES =================
        if 'atr' not in df.columns:
            if talib is not None:
                df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)
            else:
                df['atr'] = _atr_fallback(df, self.atr_period)
        
        df['n_loss'] = self.sensitivity * df['atr']
        
        # Selección de fuente de precio
        if self.use_heikin_ashi:
            ha_df = self.calculate_heikin_ashi(df)
            df['src'] = ha_df['close']
            df['ha_close'] = ha_df['close']
            df['ha_high'] = ha_df['high']
            df['ha_low'] = ha_df['low']
        else:
            df['src'] = df['close']
            df['ha_close'] = df['close']
            df['ha_high'] = df['high']
            df['ha_low'] = df['low']
            
        # ================= PARABOLIC SAR =================
        if 'sar' not in df.columns:
            if talib is not None:
                df['sar'] = talib.SAR(
                    df['high'],
                    df['low'],
                    acceleration=self.psar_start,
                    maximum=self.psar_max,
                )
            else:
                df['sar'] = _sar_fallback(df, self.psar_start, self.psar_max)
        
        df['psar_bullish'] = df['src'] > df['sar']
        df['psar_bearish'] = df['src'] < df['sar']
        df['psar_trend_change'] = df['psar_bullish'] != df['psar_bullish'].shift(1)
        
        # ================= TRAILING STOP MEJORADO =================
        df['xATRTrailingStop'] = self._calculate_trailing_stop_vectorized(df)
        
        # ================= SEÑALES CONSERVADORAS =================
        # EMA(1) = precio actual (más agresivo que usar EMA(10))
        df['ema_val'] = df['src']
        
        # Crossovers con filtros
        df['above'] = self.calculate_crossover(df['ema_val'], df['xATRTrailingStop'], df)
        df['below'] = self.calculate_crossover(df['xATRTrailingStop'], df['ema_val'], df)
        
        # Condiciones básicas
        price_above_stop = df['src'] > df['xATRTrailingStop']
        price_below_stop = df['src'] < df['xATRTrailingStop']
        
        # Filtros adicionales de calidad
        if self.trend_filter:
            # Filtro de tendencia: usar EMA 200 si existe
            if 'ema_200' in df.columns:
                strong_uptrend = df['src'] > df['ema_200'] * 1.02  # 2% por encima
                strong_downtrend = df['src'] < df['ema_200'] * 0.98  # 2% por debajo
            else:
                # Calcular EMA 200 si no existe
                if talib is not None:
                    df['ema_200'] = talib.EMA(df['src'], timeperiod=200)
                else:
                    df['ema_200'] = _ema_fallback(df['src'], 200)
                strong_uptrend = df['src'] > df['ema_200'] * 1.02
                strong_downtrend = df['src'] < df['ema_200'] * 0.98
        else:
            strong_uptrend = True
            strong_downtrend = True
        
        # Filtro de volatilidad: solo señales cuando ATR es suficiente
        atr_filter = df['atr'] > df['atr'].rolling(20).mean() * 0.8
        
        # Filtro PSAR: señales solo cuando PSAR confirma dirección (simplificado)
        psar_confirmation_long = df['psar_bullish']
        psar_confirmation_short = df['psar_bearish']
        
        # Señales finales con filtros básicos
        df['buy_signal'] = (
            price_above_stop & 
            df['above'] & 
            strong_uptrend & 
            atr_filter &
            psar_confirmation_long
        )
        
        df['sell_signal'] = (
            price_below_stop & 
            df['below'] & 
            strong_downtrend & 
            atr_filter &
            psar_confirmation_short
        )
        
        # Convertir a boolean para evitar problemas con operadores
        df['buy_signal'] = df['buy_signal'].astype(bool)
        df['sell_signal'] = df['sell_signal'].astype(bool)
        
        # Evitar señales consecutivas (método alternativo)
        for i in range(1, len(df)):
            if df['buy_signal'].iloc[i] and df['buy_signal'].iloc[i-1]:
                df.iloc[i, df.columns.get_loc('buy_signal')] = False
            if df['sell_signal'].iloc[i] and df['sell_signal'].iloc[i-1]:
                df.iloc[i, df.columns.get_loc('sell_signal')] = False
        
        # Alias para compatibilidad
        df['trailing_stop'] = df['xATRTrailingStop']
        
        return df

    def _calculate_trailing_stop_vectorized(self, df):
        """Cálculo optimizado del trailing stop"""
        trailing_stop = pd.Series(index=df.index, dtype=float)
        
        for i in range(len(df)):
            src = df['src'].iloc[i]
            n_loss = df['n_loss'].iloc[i]
            
            if i == 0:
                trailing_stop.iloc[i] = src - n_loss
                continue
                
            prev_stop = trailing_stop.iloc[i-1]
            prev_src = df['src'].iloc[i-1]
            
            # Manejo de NaN
            if pd.isna(prev_stop):
                prev_stop = src - n_loss
            
            # Lógica del Pine Script
            if src > prev_stop and prev_src > prev_stop:
                trailing_stop.iloc[i] = max(prev_stop, src - n_loss)
            elif src < prev_stop and prev_src < prev_stop:
                trailing_stop.iloc[i] = min(prev_stop, src + n_loss)
            elif src > prev_stop:
                trailing_stop.iloc[i] = src - n_loss
            else:
                trailing_stop.iloc[i] = src + n_loss
                
        return trailing_stop

    def calculate_position_size(self, capital, entry_price, stop_loss):
        """Cálculo conservador del tamaño de posición"""
        risk_amount = capital * (self.risk_percent / 100)
        risk_distance = max(abs(entry_price - stop_loss), 0.0001)
        
        # Limitar tamaño máximo de posición al 10% del capital
        max_position_value = capital * 0.1
        calculated_size = risk_amount / risk_distance
        position_value = calculated_size * entry_price
        
        if position_value > max_position_value:
            calculated_size = max_position_value / entry_price
            
        return calculated_size

    def calculate_stop_loss(self, df, position):
        """Cálculo de stop loss con margen de seguridad"""
        if position == 1:  # Long
            # Agregar 10% de margen de seguridad
            return df['ha_close'] - (df['atr'] * self.sl_atr_multiplier * 1.1)
        else:  # Short
            return df['ha_close'] + (df['atr'] * self.sl_atr_multiplier * 1.1)

    def calculate_take_profit(self, df, position):
        """Cálculo de take profit más agresivo"""
        if position == 1:  # Long
            # Incrementar take profit para mejorar ratio risk/reward
            return df['ha_close'] + (df['atr'] * self.tp_atr_multiplier * 1.2)
        else:  # Short
            return df['ha_close'] - (df['atr'] * self.tp_atr_multiplier * 1.2)

    def get_strategy_info(self):
        """Información de la estrategia conservadora"""
        return {
            'name': 'UT Bot + PSAR Conservative Strategy',
            'version': 'Conservative v1.0',
            'description': 'Implementación conservadora con filtros anti-sobretrading',
            'sensitivity': self.sensitivity,
            'atr_period': self.atr_period,
            'use_heikin_ashi': self.use_heikin_ashi,
            'risk_percent': self.risk_percent,
            'sl_atr_multiplier': self.sl_atr_multiplier,
            'tp_atr_multiplier': self.tp_atr_multiplier,
            'filters': {
                'min_atr_filter': self.min_atr_filter,
                'trend_filter': self.trend_filter,
                'psar_confirmation': True,
                'volatility_filter': True,
                'consecutive_signal_filter': True
            }
        }

    def run(self, data: pd.DataFrame, symbol: str) -> dict:
        """
        Método principal para ejecutar la estrategia conservadora
        """
        try:
            # Calcular señales usando el método existente
            df_signals = self.calculate_signals(data)

            # Simular trading
            capital = 10000  # Capital inicial
            position = 0
            trades = []
            entry_price = 0

            for i in range(len(df_signals)):
                current_price = df_signals['close'].iloc[i]

                # Verificar señales de entrada
                if position == 0:
                    if df_signals['buy_signal'].iloc[i]:
                        # Entrar en posición long
                        position = 1
                        entry_price = current_price
                        stop_loss = self.calculate_stop_loss(df_signals.iloc[i:i+1], position).iloc[0]
                        take_profit = self.calculate_take_profit(df_signals.iloc[i:i+1], position).iloc[0]

                        position_size = self.calculate_position_size(capital, entry_price, stop_loss)

                    elif df_signals['sell_signal'].iloc[i]:
                        # Entrar en posición short
                        position = -1
                        entry_price = current_price
                        stop_loss = self.calculate_stop_loss(df_signals.iloc[i:i+1], position).iloc[0]
                        take_profit = self.calculate_take_profit(df_signals.iloc[i:i+1], position).iloc[0]

                        position_size = self.calculate_position_size(capital, entry_price, stop_loss)

                # Verificar condiciones de salida
                elif position == 1:  # Posición long
                    if current_price >= take_profit or current_price <= stop_loss:
                        # Cerrar posición
                        exit_price = current_price
                        pnl = (exit_price - entry_price) * position_size
                        capital += pnl

                        trades.append({
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'type': 'long'
                        })

                        position = 0

                elif position == -1:  # Posición short
                    if current_price <= take_profit or current_price >= stop_loss:
                        # Cerrar posición
                        exit_price = current_price
                        pnl = (entry_price - exit_price) * position_size
                        capital += pnl

                        trades.append({
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'type': 'short'
                        })

                        position = 0

            # Calcular métricas
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            total_pnl = sum(t['pnl'] for t in trades)

            # Calcular drawdown máximo
            if trades:
                cumulative_pnl = [sum(t['pnl'] for t in trades[:i+1]) for i in range(len(trades))]
                peak = max(cumulative_pnl) if cumulative_pnl else 0
                max_drawdown = min(cumulative_pnl) - peak if cumulative_pnl else 0
            else:
                max_drawdown = 0.0

            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': 0.0,  # Placeholder
                'symbol': symbol,
                'trades': trades
            }

        except Exception as e:
            print(f"Error ejecutando estrategia UTBotPSARConservativeStrategy: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'symbol': symbol,
                'trades': []
            }
