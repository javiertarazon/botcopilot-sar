"""
Implementación optimizada de la estrategia UT Bot + PSAR.
Versión corregida para ser fiel al Pine Script original.
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


def _sar_fallback(df: pd.DataFrame, acceleration: float, maximum: float) -> pd.Series:
    from utils.technical_indicators_pipeline import calculate_sar

    return calculate_sar(df).fillna(0)

class UTBotPSAROptimizedStrategy:
    """
    Implementación fiel al Pine Script original de UT Bot + PSAR Strategy
    
    Parámetros del Pine Script original:
    - a (sensitivity): 1
    - c (ATR Period): 10  
    - h (Use Heikin Ashi): false
    - risk_percent: 2.0
    - tp_atr_multiplier: 2.0
    - sl_atr_multiplier: 1.5
    - psar_start: 0.02
    - psar_increment: 0.02
    - psar_max: 0.2
    """
    
    def __init__(self, 
                 sensitivity=1,           # 'a' en Pine Script
                 atr_period=10,          # 'c' en Pine Script
                 use_heikin_ashi=False,  # 'h' en Pine Script
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
        """Cálculo exacto de Heikin Ashi como en Pine Script"""
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

    def calculate_crossover(self, series1, series2):
        """
        Implementa ta.crossover() de Pine Script
        Retorna True cuando series1 cruza por encima de series2
        """
        return (series1 > series2) & (series1.shift(1) <= series2.shift(1))

    def calculate_crossunder(self, series1, series2):
        """
        Implementa ta.crossunder() de Pine Script  
        Retorna True cuando series1 cruza por debajo de series2
        """
        return (series1 < series2) & (series1.shift(1) >= series2.shift(1))

    def calculate_signals(self, df):
        """
        Implementación exacta del Pine Script UT Bot + PSAR Strategy
        """
        df = df.copy()
        
        # ================= CÁLCULOS PRINCIPALES =================
        # xATR = ta.atr(c) - Usar ATR existente o calcular
        if 'atr' not in df.columns:
            if talib is not None:
                df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.atr_period)
            else:
                df['atr'] = _atr_fallback(df, self.atr_period)
        
        # nLoss = a * xATR
        df['n_loss'] = self.sensitivity * df['atr']
        
        # Selección de fuente de precio (src)
        if self.use_heikin_ashi:
            ha_df = self.calculate_heikin_ashi(df)
            df['src'] = ha_df['close']
            # Agregar columnas HA para compatibilidad
            df['ha_close'] = ha_df['close']
            df['ha_high'] = ha_df['high']
            df['ha_low'] = ha_df['low']
        else:
            df['src'] = df['close']
            # Alias para compatibilidad
            df['ha_close'] = df['close']
            df['ha_high'] = df['high']
            df['ha_low'] = df['low']
            
        # ================= PARABOLIC SAR =================
        # Usar SAR existente o calcular
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
        
        # psar_bullish = close > psar
        df['psar_bullish'] = df['src'] > df['sar']
        df['psar_bearish'] = df['src'] < df['sar']
        
        # Detectar cambios de tendencia en el SAR (IMPLEMENTACIÓN CORRECTA)
        df['psar_trend_change'] = df['psar_bullish'] != df['psar_bullish'].shift(1)
        
        # ================= TRAILING STOP DINÁMICO =================
        # Implementación exacta del Pine Script con lógica nz()
        df['xATRTrailingStop'] = np.nan
        
        for i in range(len(df)):
            src = df['src'].iloc[i]
            n_loss = df['n_loss'].iloc[i]
            
            if i == 0:
                # Inicialización: src - n_loss para la primera barra
                df.iloc[i, df.columns.get_loc('xATRTrailingStop')] = src - n_loss
                continue
                
            prev_stop = df['xATRTrailingStop'].iloc[i-1] 
            prev_src = df['src'].iloc[i-1]
            
            # nz() equivalente: si prev_stop es NaN, usar 0
            if pd.isna(prev_stop):
                prev_stop = 0
            
            # Lógica exacta del Pine Script:
            # src > nz(xATRTrailingStop) and src[1] > nz(xATRTrailingStop) ? 
            #   math.max(nz(xATRTrailingStop), src - nLoss) :
            # src < nz(xATRTrailingStop) and src[1] < nz(xATRTrailingStop) ? 
            #   math.min(nz(xATRTrailingStop), src + nLoss) :
            # src > nz(xATRTrailingStop) ? src - nLoss : src + nLoss
            
            if src > prev_stop and prev_src > prev_stop:
                new_stop = max(prev_stop, src - n_loss)
            elif src < prev_stop and prev_src < prev_stop:
                new_stop = min(prev_stop, src + n_loss)
            elif src > prev_stop:
                new_stop = src - n_loss
            else:
                new_stop = src + n_loss
                
            df.iloc[i, df.columns.get_loc('xATRTrailingStop')] = new_stop
        
        # ================= SEÑALES DE ENTRADA =================
        # ema_val = ta.ema(src, 1) - EMA de 1 periodo = precio actual
        df['ema_val'] = df['src']  # EMA(1) = precio actual
        
        # above = ta.crossover(ema_val, xATRTrailingStop)
        df['above'] = self.calculate_crossover(df['ema_val'], df['xATRTrailingStop'])
        
        # below = ta.crossover(xATRTrailingStop, ema_val)  
        df['below'] = self.calculate_crossover(df['xATRTrailingStop'], df['ema_val'])
        
        # buy_signal = src > xATRTrailingStop and above
        df['buy_signal'] = (df['src'] > df['xATRTrailingStop']) & df['above']
        
        # sell_signal = src < xATRTrailingStop and below
        df['sell_signal'] = (df['src'] < df['xATRTrailingStop']) & df['below']
        
        # Agregar columnas de trailing stop como alias
        df['trailing_stop'] = df['xATRTrailingStop']
        
        return df

    def calculate_position_size(self, capital, entry_price, stop_loss):
        """
        Cálculo exacto del Pine Script:
        risk_amount = capital * (risk_percent / 100)
        position_size = risk_amount / math.max(math.abs(entry_price - stop_loss), 0.0001)
        """
        risk_amount = capital * (self.risk_percent / 100)
        risk_distance = max(abs(entry_price - stop_loss), 0.0001)
        return risk_amount / risk_distance

    def calculate_stop_loss(self, df, position):
        """
        Cálculo exacto del Pine Script:
        Long: entry_price - (xATR * sl_atr_multiplier)
        Short: entry_price + (xATR * sl_atr_multiplier)
        """
        if position == 1:  # Long
            return df['ha_close'] - (df['atr'] * self.sl_atr_multiplier)
        else:  # Short
            return df['ha_close'] + (df['atr'] * self.sl_atr_multiplier)

    def calculate_take_profit(self, df, position):
        """
        Cálculo exacto del Pine Script:
        Long: entry_price + (xATR * tp_atr_multiplier)  
        Short: entry_price - (xATR * tp_atr_multiplier)
        """
        if position == 1:  # Long
            return df['ha_close'] + (df['atr'] * self.tp_atr_multiplier)
        else:  # Short
            return df['ha_close'] - (df['atr'] * self.tp_atr_multiplier)

    def get_strategy_info(self):
        """Información de la estrategia como en el Pine Script"""
        return {
            'name': 'UT Bot + PSAR Strategy',
            'version': 'Optimized v1.0',
            'sensitivity': self.sensitivity,
            'atr_period': self.atr_period,
            'use_heikin_ashi': self.use_heikin_ashi,
            'risk_percent': self.risk_percent,
            'sl_atr_multiplier': self.sl_atr_multiplier,
            'tp_atr_multiplier': self.tp_atr_multiplier,
            'psar_start': self.psar_start,
            'psar_increment': self.psar_increment,
            'psar_max': self.psar_max
        }

    def run(self, data: pd.DataFrame, symbol: str) -> dict:
        """
        Método principal para ejecutar la estrategia optimizada
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
            print(f"Error ejecutando estrategia UTBotPSAROptimizedStrategy: {e}")
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
