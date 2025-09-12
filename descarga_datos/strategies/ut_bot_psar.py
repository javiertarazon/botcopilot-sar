"""
Implementación de la estrategia UT Bot + PSAR.
"""
import numpy as np
import pandas as pd
import talib
from typing import Dict

class UTBotPSARStrategy:
    def __init__(self, 
                 sensitivity=1,
                 atr_period=10,
                 use_heikin_ashi=False,
                 risk_percent=2.0,
                 tp_atr_multiplier=2.0,
                 sl_atr_multiplier=1.5,
                 psar_start=0.02,
                 psar_increment=0.02,
                 psar_max=0.2):
        self.sensitivity = sensitivity
        self.atr_period = atr_period
        self.use_heikin_ashi = use_heikin_ashi
        self.risk_percent = risk_percent
        self.tp_atr_multiplier = tp_atr_multiplier
        self.sl_atr_multiplier = sl_atr_multiplier
        self.psar_start = psar_start
        self.psar_increment = psar_increment
        self.psar_max = psar_max

    def calculate_heikin_ashi(self, df):
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

    def calculate_signals(self, df):
        """
        Calcula las señales usando los indicadores ya existentes en los datos.
        Los datos deben contener: atr, sar, ema_10, ema_20, ema_200
        """
        # Hacer copia para evitar warnings de pandas
        df = df.copy()
        
        # Calcular indicadores faltantes si no existen
        if 'ema_10' not in df.columns:
            df.loc[:, 'ema_10'] = df['close'].ewm(span=10).mean()
        if 'ema_20' not in df.columns:
            df.loc[:, 'ema_20'] = df['close'].ewm(span=20).mean()
        if 'ema_200' not in df.columns:
            df.loc[:, 'ema_200'] = df['close'].ewm(span=200).mean()
        if 'atr' not in df.columns:
            # Calcular ATR si no existe
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df.loc[:, 'atr'] = true_range.rolling(window=14).mean()
        if 'sar' not in df.columns:
            # Calcular PSAR simplificado si no existe
            df.loc[:, 'sar'] = self._calculate_psar_simple(df)

        if self.use_heikin_ashi:
            df = self.calculate_heikin_ashi(df)
            price_col = 'ha_close'
        else:
            # Agregar columnas como alias para compatibilidad
            df.loc[:, 'ha_close'] = df['close']
            df.loc[:, 'ha_high'] = df['high']
            df.loc[:, 'ha_low'] = df['low']
            price_col = 'close'

        # Usar ATR existente
        df.loc[:, 'n_loss'] = self.sensitivity * df['atr']

        # Usar SAR existente
        df.loc[:, 'psar'] = df['sar']  # Renombrar para mantener consistencia con el código
        df.loc[:, 'psar_bullish'] = df[price_col] > df['sar']
        df.loc[:, 'psar_bearish'] = df[price_col] < df['sar']
        df.loc[:, 'psar_trend_change'] = df['psar_bullish'] != df['psar_bullish'].shift(1)

        # Calcular trailing stop
        trailing_stop = pd.Series(index=df.index, dtype=float)
        current_stop = df['ha_close'].iloc[0]
        
        for i in range(len(df)):
            price = df[price_col].iloc[i]
            n_loss = df['n_loss'].iloc[i]
            
            if i == 0:
                trailing_stop.iloc[i] = price - n_loss if price > current_stop else price + n_loss
                continue
                
            prev_stop = trailing_stop.iloc[i-1]
            
            if price > prev_stop and df[price_col].iloc[i-1] > prev_stop:
                current_stop = max(prev_stop, price - n_loss)
            elif price < prev_stop and df[price_col].iloc[i-1] < prev_stop:
                current_stop = min(prev_stop, price + n_loss)
            else:
                current_stop = price - n_loss if price > prev_stop else price + n_loss
                
            trailing_stop.iloc[i] = current_stop
            
        df = df.copy()  # Crear una copia para evitar SettingWithCopyWarning
        df['trailing_stop'] = trailing_stop

        # Calcular señales de entrada usando EMA existente (usaremos ema_10 como señal rápida)
        df['above'] = (df['ema_10'] > df['trailing_stop']) & (df['ema_10'].shift(1) <= df['trailing_stop'].shift(1))
        df['below'] = (df['ema_10'] < df['trailing_stop']) & (df['ema_10'].shift(1) >= df['trailing_stop'].shift(1))

        # Confirmar señales con tendencia (usando ema_200 como referencia de tendencia)
        long_trend = df[price_col] > df['ema_200']
        short_trend = df[price_col] < df['ema_200']

        df['buy_signal'] = (df[price_col] > df['trailing_stop']) & df['above'] & long_trend
        df['sell_signal'] = (df[price_col] < df['trailing_stop']) & df['below'] & short_trend

        return df

    def calculate_position_size(self, capital, entry_price, stop_loss):
        risk_amount = capital * (self.risk_percent / 100)
        return risk_amount / max(abs(entry_price - stop_loss), 0.0001)

    def calculate_stop_loss(self, df, position):
        """
        Calcula el stop loss basado en ATR
        position: 1 para long, -1 para short
        """
        if position == 1:
            return df['ha_close'] - (df['atr'] * self.sl_atr_multiplier)
        else:
            return df['ha_close'] + (df['atr'] * self.sl_atr_multiplier)

    def calculate_take_profit(self, df, position):
        """
        Calcula el take profit basado en ATR
        position: 1 para long, -1 para short
        """
        if position == 1:
            return df['ha_close'] + (df['atr'] * self.tp_atr_multiplier)
        else:
            return df['ha_close'] - (df['atr'] * self.tp_atr_multiplier)

    def run(self, data, symbol):
        """
        Ejecuta la estrategia y devuelve los resultados del backtesting
        """
        try:
            # Calcular señales
            df = self.calculate_signals(data.copy())
            
            # Inicializar variables de trading
            capital = 10000.0  # Capital inicial
            position = 0  # 0: sin posición, 1: long, -1: short
            entry_price = 0.0
            stop_loss = 0.0
            take_profit = 0.0
            trades = []
            
            # Simular trading
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                
                # Verificar señales de entrada
                if position == 0:
                    if df['buy_signal'].iloc[i]:
                        # Entrar en posición long
                        position = 1
                        entry_price = current_price
                        stop_loss = self.calculate_stop_loss(df.iloc[i:i+1], position).iloc[0]
                        take_profit = self.calculate_take_profit(df.iloc[i:i+1], position).iloc[0]
                        
                        position_size = self.calculate_position_size(capital, entry_price, stop_loss)
                        
                    elif df['sell_signal'].iloc[i]:
                        # Entrar en posición short
                        position = -1
                        entry_price = current_price
                        stop_loss = self.calculate_stop_loss(df.iloc[i:i+1], position).iloc[0]
                        take_profit = self.calculate_take_profit(df.iloc[i:i+1], position).iloc[0]
                        
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
            
            # Calcular métricas avanzadas
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            total_pnl = sum(t['pnl'] for t in trades)
            
            # Construir equity curve correctamente
            capital = 10000.0
            equity_curve = [capital]
            for trade in trades:
                capital += trade['pnl']
                equity_curve.append(capital)
            
            # Calcular drawdown máximo correctamente
            if len(equity_curve) > 1:
                equity_series = pd.Series(equity_curve)
                peak = equity_series.expanding().max()
                drawdown = equity_series - peak
                max_drawdown = abs(drawdown.min())
                max_drawdown_percent = (max_drawdown / 10000.0) * 100
            else:
                max_drawdown = 0.0
                max_drawdown_percent = 0.0
            
            # Calcular Sharpe ratio correctamente
            if len(equity_curve) > 2:
                equity_series = pd.Series(equity_curve)
                returns = equity_series.pct_change().dropna()
                if returns.std() > 0:
                    sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_return': (total_pnl / 10000.0) * 100,  # Agregar total_return
                'max_drawdown': max_drawdown,
                'max_drawdown_percent': max_drawdown_percent,
                'sharpe_ratio': sharpe_ratio,
                'symbol': symbol,
                'trades': trades,
                'compensated_trades': 0,
                'compensation_success_rate': 0.0,
                'total_compensation_pnl': 0.0,
                'avg_compensation_pnl': 0.0,
                'compensation_ratio': 0.0,
                'net_compensation_impact': 0.0,
                'adjusted_total_pnl': total_pnl
            }
            
        except Exception as e:
            print(f"Error ejecutando estrategia UTBotPSARStrategy: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_return': 0.0,  # Agregar total_return en caso de error
                'max_drawdown': 0.0,
                'max_drawdown_percent': 0.0,
                'sharpe_ratio': 0.0,
                'symbol': symbol,
                'trades': [],
                'compensated_trades': 0,
                'compensation_success_rate': 0.0,
                'total_compensation_pnl': 0.0,
                'avg_compensation_pnl': 0.0,
                'compensation_ratio': 0.0,
                'net_compensation_impact': 0.0,
                'adjusted_total_pnl': 0.0
            }
    
    def _calculate_psar_simple(self, df):
        """Calcula PSAR simplificado"""
        high = df['high'].values
        low = df['low'].values
        
        psar = np.zeros(len(df))
        psar[0] = low[0]
        
        acceleration = 0.02
        max_acceleration = 0.2
        
        trend = 1
        extreme_point = high[0]
        
        for i in range(1, len(df)):
            psar[i] = psar[i-1] + acceleration * (extreme_point - psar[i-1])
            
            if trend == 1:
                if low[i] <= psar[i]:
                    trend = -1
                    psar[i] = extreme_point
                    extreme_point = low[i]
                    acceleration = 0.02
                else:
                    if high[i] > extreme_point:
                        extreme_point = high[i]
                        acceleration = min(acceleration + 0.02, max_acceleration)
            else:
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

    def run_backtest(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Ejecuta backtest de la estrategia"""
        try:
            # Calcular indicadores si no existen
            if 'atr' not in df.columns:
                df = self.calculate_indicators(df)
            
            # Calcular señales
            signals = self.calculate_signals(df)
            
            # Simular trades
            capital = 10000
            position = 0
            trades = []
            entry_price = 0
            
            for i in range(len(df)):
                signal = signals.iloc[i] if i < len(signals) else 0
                
                if signal == 1 and position == 0:  # Buy
                    position = capital / df.iloc[i]['close']
                    entry_price = df.iloc[i]['close']
                    capital = 0
                    trades.append({
                        'type': 'buy',
                        'price': entry_price,
                        'timestamp': df.index[i]
                    })
                    
                elif signal == -1 and position > 0:  # Sell
                    exit_price = df.iloc[i]['close']
                    capital = position * exit_price
                    pnl = (exit_price - entry_price) / entry_price * 100
                    position = 0
                    trades.append({
                        'type': 'sell',
                        'price': exit_price,
                        'pnl': pnl,
                        'timestamp': df.index[i]
                    })
            
            # Calcular métricas
            total_return = (capital - 10000) / 10000 * 100 if capital > 0 else 0
            total_trades = len(trades)
            
            return {
                'total_return': total_return,
                'total_trades': total_trades,
                'final_capital': capital,
                'trades': trades
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'total_return': 0,
                'total_trades': 0
            }
