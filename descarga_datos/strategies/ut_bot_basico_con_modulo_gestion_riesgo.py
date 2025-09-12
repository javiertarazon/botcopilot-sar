"""
Estrategia UT Bot Básica con Módulo Avanzado de Gestión de Riesgo
=================================================================

Versión mejorada de la estrategia UT Bot PSAR que integra el sistema
avanzado de gestión de riesgo con compensación automática, Kelly Criterion,
análisis de correlación y otras funcionalidades profesionales.

Características principales:
- ✅ Lógica UT Bot PSAR original
- ✅ Sistema de compensación automática (3x lot sizing)
- ✅ Kelly Criterion para dimensionamiento óptimo
- ✅ Análisis de correlación entre activos
- ✅ Volatility-adjusted position sizing
- ✅ Risk parity calculations
- ✅ Límites de exposición por sector
- ✅ Alertas automáticas del sistema de riesgo
"""

import numpy as np
import pandas as pd
import talib
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# Importar el módulo de gestión de riesgo avanzado
from risk_management.risk_management import AdvancedRiskManager, RiskConfig

class UTBotBasicoConModuloGestionRiesgo:
    """
    Estrategia UT Bot PSAR con integración completa del módulo de gestión de riesgo avanzado
    """

    def __init__(self,
                 sensitivity=1.2,  # Reducido de 2.5 a 1.2 para menos señales falsas
                 atr_period=14,   # Mantenido en 14 para estabilidad
                 use_heikin_ashi=False,
                 risk_percent=2.5,  # Ajustado de 3.0% a 2.5% para balance
                 tp_atr_multiplier=4.0,  # Aumentado de 3.0 a 4.0 para mejor ratio R:R
                 sl_atr_multiplier=0.7,  # Ajustado de 1.0 a 0.7 para mejor win rate
                 psar_start=0.02,
                 psar_increment=0.02,
                 psar_max=0.2):
        # Parámetros técnicos de la estrategia
        self.sensitivity = sensitivity
        self.atr_period = atr_period
        self.use_heikin_ashi = use_heikin_ashi
        self.risk_percent = risk_percent
        self.tp_atr_multiplier = tp_atr_multiplier
        self.sl_atr_multiplier = sl_atr_multiplier
        self.psar_start = psar_start
        self.psar_increment = psar_increment
        self.psar_max = psar_max

        # Inicializar el módulo de gestión de riesgo avanzado
        self.risk_manager = AdvancedRiskManager()

        # Configurar el risk manager con parámetros más agresivos para rentabilidad
        self.risk_manager.risk_config.risk_per_trade = risk_percent / 100
        self.risk_manager.risk_config.stop_loss_atr_multiplier = sl_atr_multiplier
        self.risk_manager.risk_config.take_profit_atr_multiplier = tp_atr_multiplier
        self.risk_manager.risk_config.kelly_fraction = 0.25  # Aumentado de 0.1 a 0.25 para más agresividad
        self.risk_manager.risk_config.max_drawdown = 0.25  # Aumentado de 0.15 a 0.25 para más tolerancia
        self.risk_manager.risk_config.compensation_enabled = True
        self.risk_manager.risk_config.compensation_threshold = 0.05  # Aumentado de 0.03 a 0.05 para activar menos compensaciones
        self.risk_manager.risk_config.compensation_risk_multiplier = 2.0  # Reducido de 1.5 a 2.0 para compensaciones más agresivas

        # Inicializar atributos faltantes del risk manager
        if not hasattr(self.risk_manager, 'trade_history'):
            self.risk_manager.trade_history = []
        if not hasattr(self.risk_manager, 'daily_returns'):
            self.risk_manager.daily_returns = []
        if not hasattr(self.risk_manager, 'max_positions'):
            self.risk_manager.max_positions = 15  # Aumentado de 10 a 15 para más posiciones
        if not hasattr(self.risk_manager, 'max_sector_exposure'):
            self.risk_manager.max_sector_exposure = 0.4  # Aumentado de 0.3 a 0.4 para más exposición por sector

        # Variables de estado de la estrategia
        self.current_positions = {}
        self.trade_history = []
        self.daily_returns = []

        print("🛡️ Estrategia UT Bot Básica con Módulo de Gestión de Riesgo inicializada")
        print("✅ Sistema de compensación automática: ACTIVADO")
        print("✅ Kelly Criterion: ACTIVADO")
        print("✅ Análisis de correlación: ACTIVADO")
        print("✅ Volatility-adjusted sizing: ACTIVADO")

    def calculate_heikin_ashi(self, df):
        """Calcula velas Heikin-Ashi"""
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

        # Calcular trailing stop más agresivo
        trailing_stop = pd.Series(index=df.index, dtype=float)
        current_stop = df[price_col].iloc[0]

        for i in range(len(df)):
            price = df[price_col].iloc[i]
            n_loss = df['n_loss'].iloc[i]

            if i == 0:
                trailing_stop.iloc[i] = price - n_loss if price > current_stop else price + n_loss
                continue

            prev_stop = trailing_stop.iloc[i-1]

            # Trailing stop más agresivo - se ajusta más rápido
            if price > prev_stop:
                current_stop = max(prev_stop, price - n_loss * 0.8)  # Más agresivo
            elif price < prev_stop:
                current_stop = min(prev_stop, price + n_loss * 0.8)  # Más agresivo
            else:
                current_stop = price - n_loss if price > prev_stop else price + n_loss

            trailing_stop.iloc[i] = current_stop

        df = df.copy()
        df['trailing_stop'] = trailing_stop

        # Calcular señales de entrada más agresivas
        df['above'] = df[price_col] > df['trailing_stop']  # Simplificado
        df['below'] = df[price_col] < df['trailing_stop']  # Simplificado        # Confirmar señales con tendencia (relajado para más señales)
        long_trend = (df[price_col] > df['ema_200']) | (df['ema_10'] > df['ema_20'])  # Más flexible
        short_trend = (df[price_col] < df['ema_200']) | (df['ema_10'] < df['ema_20'])  # Más flexible

        # Señales más agresivas - sin requerir cruce de EMA para trailing stop
        df['buy_signal'] = (df[price_col] > df['trailing_stop']) & long_trend
        df['sell_signal'] = (df[price_col] < df['trailing_stop']) & short_trend

        return df

    def calculate_position_size_advanced(self, symbol: str, entry_price: float,
                                      stop_loss_price: float, atr_value: float = None,
                                      signal_strength: float = 1.0) -> Dict[str, Any]:
        """
        Calcula el tamaño de posición usando el módulo avanzado de gestión de riesgo
        """
        return self.risk_manager.calculate_position_size(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            signal_strength=signal_strength,
            atr_value=atr_value
        )

    def can_open_position(self, symbol: str, position_value: float) -> tuple[bool, str]:
        """
        Verifica si se puede abrir una nueva posición usando el risk manager
        """
        return self.risk_manager.can_open_new_position(symbol, position_value)

    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de riesgo del módulo avanzado
        """
        return self.risk_manager.get_risk_metrics()

    def process_risk_management_cycle(self, market_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Ejecuta un ciclo completo de gestión de riesgo
        """
        return self.risk_manager.process_risk_management_cycle(market_data)

    def get_compensation_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado del sistema de compensación
        """
        return self.risk_manager.get_compensation_status()

    def run(self, data, symbol):
        """
        Ejecuta la estrategia y devuelve los resultados del backtesting
        con integración completa del módulo de gestión de riesgo avanzado
        """
        try:
            print(f"🚀 Ejecutando estrategia UT Bot con Gestión de Riesgo Avanzado para {symbol}")

            # Calcular señales
            df = self.calculate_signals(data.copy())

            # Inicializar variables de trading
            trades = []
            compensation_trades = []
            total_compensation_pnl = 0.0
            compensation_success_count = 0

            # Simular trading con gestión de riesgo avanzada
            for i in range(len(df)):
                current_price = df['close'].iloc[i]
                current_atr = df['atr'].iloc[i] if 'atr' in df.columns else 0.0

                # Verificar señales de entrada
                if df['buy_signal'].iloc[i] and symbol not in self.current_positions:
                    # Calcular stop loss y take profit
                    stop_loss_price = current_price - (current_atr * self.sl_atr_multiplier)
                    take_profit_price = current_price + (current_atr * self.tp_atr_multiplier)

                    # Usar el módulo avanzado para calcular tamaño de posición
                    position_calc = self.calculate_position_size_advanced(
                        symbol=symbol,
                        entry_price=current_price,
                        stop_loss_price=stop_loss_price,
                        atr_value=current_atr,
                        signal_strength=1.0
                    )

                    if 'error' not in position_calc:
                        position_size = position_calc['recommended_size']

                        # Verificar si se puede abrir la posición
                        position_value = position_size * current_price
                        can_open, reason = self.can_open_position(symbol, position_value)

                        if can_open:
                            # Abrir posición long
                            self.current_positions[symbol] = {
                                'type': 'long',
                                'entry_price': current_price,
                                'quantity': position_size,
                                'stop_loss': stop_loss_price,
                                'take_profit': take_profit_price,
                                'entry_time': df.index[i] if hasattr(df.index[i], 'timestamp') else datetime.now(),
                                'atr_value': current_atr
                            }

                            print(f"📈 LONG {symbol}: Entry={current_price:.4f}, Size={position_size:.6f}, SL={stop_loss_price:.4f}, TP={take_profit_price:.4f}")
                        else:
                            print(f"⚠️ No se puede abrir posición {symbol}: {reason}")

                elif df['sell_signal'].iloc[i] and symbol not in self.current_positions:
                    # Calcular stop loss y take profit
                    stop_loss_price = current_price + (current_atr * self.sl_atr_multiplier)
                    take_profit_price = current_price - (current_atr * self.tp_atr_multiplier)

                    # Usar el módulo avanzado para calcular tamaño de posición
                    position_calc = self.calculate_position_size_advanced(
                        symbol=symbol,
                        entry_price=current_price,
                        stop_loss_price=stop_loss_price,
                        atr_value=current_atr,
                        signal_strength=1.0
                    )

                    if 'error' not in position_calc:
                        position_size = position_calc['recommended_size']

                        # Verificar si se puede abrir la posición
                        position_value = position_size * current_price
                        can_open, reason = self.can_open_position(symbol, position_value)

                        if can_open:
                            # Abrir posición short
                            self.current_positions[symbol] = {
                                'type': 'short',
                                'entry_price': current_price,
                                'quantity': position_size,
                                'stop_loss': stop_loss_price,
                                'take_profit': take_profit_price,
                                'entry_time': df.index[i] if hasattr(df.index[i], 'timestamp') else datetime.now(),
                                'atr_value': current_atr
                            }

                            print(f"📉 SHORT {symbol}: Entry={current_price:.4f}, Size={position_size:.6f}, SL={stop_loss_price:.4f}, TP={take_profit_price:.4f}")
                        else:
                            print(f"⚠️ No se puede abrir posición {symbol}: {reason}")

                # Verificar condiciones de salida para posiciones abiertas
                if symbol in self.current_positions:
                    position = self.current_positions[symbol]

                    should_close = False
                    exit_reason = ""

                    if position['type'] == 'long':
                        if current_price >= position['take_profit']:
                            should_close = True
                            exit_reason = "Take Profit"
                        elif current_price <= position['stop_loss']:
                            should_close = True
                            exit_reason = "Stop Loss"
                    else:  # short
                        if current_price <= position['take_profit']:
                            should_close = True
                            exit_reason = "Take Profit"
                        elif current_price >= position['stop_loss']:
                            should_close = True
                            exit_reason = "Stop Loss"

                    if should_close:
                        # Calcular P&L
                        if position['type'] == 'long':
                            pnl = (current_price - position['entry_price']) * position['quantity']
                        else:
                            pnl = (position['entry_price'] - current_price) * position['quantity']

                        # Registrar trade
                        trade = {
                            'entry_price': position['entry_price'],
                            'exit_price': current_price,
                            'pnl': pnl,
                            'type': position['type'],
                            'exit_reason': exit_reason,
                            'quantity': position['quantity'],
                            'symbol': symbol,
                            'entry_time': position['entry_time'],
                            'exit_time': df.index[i] if hasattr(df.index[i], 'timestamp') else datetime.now()
                        }

                        trades.append(trade)

                        # Actualizar el historial de trades para el risk manager
                        self.trade_history.append({
                            'symbol': symbol,
                            'return_pct': (pnl / (position['entry_price'] * position['quantity'])) * 100,
                            'timestamp': trade['exit_time']
                        })

                        print(f"💰 CERRADO {symbol} {position['type'].upper()}: Exit={current_price:.4f}, P&L={pnl:.2f}, Reason={exit_reason}")

                        # Cerrar posición
                        del self.current_positions[symbol]

                # Ejecutar ciclo de gestión de riesgo cada cierto número de iteraciones
                if i % 10 == 0:  # Cada 10 velas
                    market_data = {symbol: current_price}
                    risk_cycle_result = self.process_risk_management_cycle(market_data)

                    if not risk_cycle_result['success']:
                        print(f"⚠️ Error en ciclo de gestión de riesgo: {risk_cycle_result.get('error', 'Unknown')}")

            # Calcular métricas finales
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            total_pnl = sum(t['pnl'] for t in trades)

            # Calcular retorno total
            total_return = (total_pnl / self.risk_manager.risk_config.initial_capital) * 100

            # Calcular drawdown máximo
            if len(trades) > 0:
                capital = self.risk_manager.risk_config.initial_capital
                equity_curve = [capital]
                for trade in trades:
                    capital += trade['pnl']
                    equity_curve.append(capital)

                if len(equity_curve) > 1:
                    equity_series = pd.Series(equity_curve)
                    peak = equity_series.expanding().max()
                    drawdown = equity_series - peak
                    max_drawdown = abs(drawdown.min())
                    max_drawdown_percent = (max_drawdown / self.risk_manager.risk_config.initial_capital) * 100
                else:
                    max_drawdown = 0.0
                    max_drawdown_percent = 0.0
            else:
                max_drawdown = 0.0
                max_drawdown_percent = 0.0

            # Calcular Sharpe ratio
            if len(trades) > 2:
                equity_series = pd.Series([self.risk_manager.risk_config.initial_capital] + [t['pnl'] for t in trades])
                returns = equity_series.pct_change().dropna()
                if returns.std() > 0:
                    sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0

            # Obtener métricas del risk manager
            risk_metrics = self.get_risk_metrics()
            compensation_status = self.get_compensation_status()

            print(f"📊 Resultados para {symbol}:")
            print(f"   Trades: {total_trades}, Win Rate: {win_rate:.1%}")
            print(f"   P&L Total: ${total_pnl:.2f}, Retorno: {total_return:.2f}%")
            print(f"   Max Drawdown: {max_drawdown_percent:.1f}%")
            print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")

            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_return': total_return,
                'max_drawdown': max_drawdown,
                'max_drawdown_percent': max_drawdown_percent,
                'sharpe_ratio': sharpe_ratio,
                'symbol': symbol,
                'trades': trades,
                'compensated_trades': compensation_status.get('active_compensations', 0),
                'compensation_success_rate': compensation_status.get('compensation_success_rate', 0.0),
                'total_compensation_pnl': compensation_status.get('total_compensation_pnl', 0.0),
                'avg_compensation_pnl': compensation_status.get('avg_compensation_pnl', 0.0),
                'compensation_ratio': compensation_status.get('compensation_ratio', 0.0),
                'net_compensation_impact': compensation_status.get('net_compensation_impact', 0.0),
                'adjusted_total_pnl': total_pnl,
                'risk_metrics': risk_metrics,
                'compensation_status': compensation_status
            }

        except Exception as e:
            print(f"❌ Error ejecutando estrategia con gestión de riesgo avanzado: {e}")
            import traceback
            traceback.print_exc()

            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_return': 0.0,
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
                'adjusted_total_pnl': 0.0,
                'error': str(e)
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