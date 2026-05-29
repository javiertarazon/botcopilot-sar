"""
ESTRATEGIA UNIFICADA UT BOT + PSAR
===================================

Estrategia unificada que combina las mejores características de todas las estrategias existentes.
Utiliza los módulos externos de indicadores técnicos y gestión de riesgo.

Características principales:
- Señales UT Bot optimizadas
- Filtros avanzados de calidad
- Gestión de riesgo integrada
- Configuración adaptable por símbolo
- Sistema de compensación opcional
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
from enum import Enum

from indicators.technical_indicators import TechnicalIndicators
from risk_management.risk_management import AdvancedRiskManager, RiskConfig
from config.config import Config


class TradingStyle(Enum):
    """Estilos de trading disponibles"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    ULTRA_AGGRESSIVE = "ultra_aggressive"


class MarketRegime(Enum):
    """Regímenes de mercado detectados"""
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"


@dataclass
class UnifiedStrategyConfig:
    """Configuración unificada de la estrategia"""

    # Parámetros base UT Bot
    sensitivity: int = 2
    atr_period: int = 14
    use_heikin_ashi: bool = False

    # Gestión de riesgo
    risk_per_trade: float = 0.02  # 2%
    max_drawdown: float = 0.15    # 15%
    stop_loss_atr_multiplier: float = 1.5
    take_profit_atr_multiplier: float = 3.0

    # Parámetros PSAR
    psar_acceleration: float = 0.02
    psar_maximum: float = 0.2

    # Filtros de calidad (de estrategia conservadora)
    use_trend_filter: bool = True
    use_volatility_filter: bool = True
    use_volume_filter: bool = True
    min_volume_multiplier: float = 1.2

    # Filtros avanzados (de estrategia avanzada)
    use_market_regime_filter: bool = True
    use_momentum_confluence: bool = True
    adx_threshold: float = 25.0

    # Configuración por símbolo
    symbol_configs: Dict[str, Dict] = field(default_factory=dict)

    # Sistema de compensación
    compensation_enabled: bool = False  # Deshabilitado por defecto según requerimiento del usuario

    # Estilo de trading
    trading_style: TradingStyle = TradingStyle.MODERATE


class UnifiedUTBotPSARStrategy:
    """
    Estrategia unificada UT Bot + PSAR que combina todas las mejores características
    de las estrategias existentes, utilizando módulos externos para indicadores y riesgo.
    """

    def __init__(self, config: UnifiedStrategyConfig = None):
        self.config = config or UnifiedStrategyConfig()
        self.logger = logging.getLogger(__name__)

        # Inicializar módulos externos
        self.config_manager = Config()
        self.indicators = TechnicalIndicators(self.config_manager)
        self.risk_manager = AdvancedRiskManager()
        self.risk_manager.set_config_manager(self.config_manager)

        # Estado interno
        self.current_symbol = None
        self.current_regime = MarketRegime.RANGING

        # Configurar según estilo de trading
        self._configure_for_trading_style()

        self.logger.info(f"[OK] Estrategia Unificada UT Bot + PSAR inicializada - Estilo: {self.config.trading_style.value}")

    def _configure_for_trading_style(self):
        """Configura parámetros según el estilo de trading seleccionado"""
        if self.config.trading_style == TradingStyle.CONSERVATIVE:
            self.config.sensitivity = 1
            self.config.risk_per_trade = 0.01
            self.config.stop_loss_atr_multiplier = 2.0
            self.config.take_profit_atr_multiplier = 2.0
            self.config.use_trend_filter = True
            self.config.use_volatility_filter = True
            self.config.use_market_regime_filter = True
            self.config.use_momentum_confluence = False  # Más permisivo
            self.config.min_volume_multiplier = 1.0  # Más permisivo
            self.config.adx_threshold = 20.0  # Más bajo para más señales

        elif self.config.trading_style == TradingStyle.MODERATE:
            self.config.sensitivity = 2
            self.config.risk_per_trade = 0.02
            self.config.stop_loss_atr_multiplier = 1.5
            self.config.take_profit_atr_multiplier = 3.0
            self.config.use_trend_filter = True
            self.config.use_volatility_filter = True
            self.config.use_market_regime_filter = False
            self.config.use_momentum_confluence = True
            self.config.min_volume_multiplier = 1.2
            self.config.adx_threshold = 25.0

        elif self.config.trading_style == TradingStyle.AGGRESSIVE:
            self.config.sensitivity = 3
            self.config.risk_per_trade = 0.03
            self.config.stop_loss_atr_multiplier = 1.0
            self.config.take_profit_atr_multiplier = 4.0
            self.config.use_trend_filter = False
            self.config.use_volatility_filter = False
            self.config.use_market_regime_filter = False
            self.config.use_momentum_confluence = False
            self.config.min_volume_multiplier = 1.5
            self.config.adx_threshold = 30.0

        elif self.config.trading_style == TradingStyle.ULTRA_AGGRESSIVE:
            self.config.sensitivity = 4
            self.config.risk_per_trade = 0.05
            self.config.stop_loss_atr_multiplier = 0.8
            self.config.take_profit_atr_multiplier = 5.0
            self.config.use_trend_filter = False
            self.config.use_volatility_filter = False
            self.config.use_market_regime_filter = False
            self.config.use_momentum_confluence = False
            self.config.min_volume_multiplier = 2.0
            self.config.adx_threshold = 35.0

    def _get_symbol_config(self, symbol: str) -> Dict:
        """Obtiene configuración específica para un símbolo"""
        return self.config.symbol_configs.get(symbol, {})

    def _detect_market_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Detecta el régimen de mercado actual usando indicadores"""
        try:
            # Calcular indicadores necesarios
            adx = self.indicators.calculate_adx(df)
            ema_200 = self.indicators.calculate_ema(df, 200)
            volatility = self.indicators.calculate_volatility(df)

            current_adx = adx.iloc[-1] if not adx.empty else 0
            current_price = df['close'].iloc[-1]
            ema_200_value = ema_200.iloc[-1] if not ema_200.empty else current_price
            current_volatility = volatility.iloc[-1] if not volatility.empty else 0

            # Lógica de detección de régimen
            if current_adx > 30:  # Mercado trending
                if current_price > ema_200_value:
                    return MarketRegime.TRENDING_BULL
                else:
                    return MarketRegime.TRENDING_BEAR
            else:  # Mercado ranging
                if current_volatility > volatility.mean() * 1.5:  # Alta volatilidad
                    return MarketRegime.HIGH_VOLATILITY
                else:
                    return MarketRegime.RANGING

        except Exception as e:
            self.logger.error(f"Error detectando régimen de mercado: {e}")
            return MarketRegime.RANGING

    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos los indicadores necesarios usando el módulo de indicadores"""
        try:
            # Copiar dataframe original
            data = df.copy()

            # Calcular indicadores básicos
            data['atr'] = self.indicators.calculate_atr(data)
            data['sar'] = self.indicators.calculate_sar(data)
            data['adx'] = self.indicators.calculate_adx(data)
            data['ema_10'] = self.indicators.calculate_ema(data, 10)
            data['ema_20'] = self.indicators.calculate_ema(data, 20)
            data['ema_200'] = self.indicators.calculate_ema(data, 200)
            data['volatility'] = self.indicators.calculate_volatility(data)

            # Selección de fuente de precio (src) - debe estar disponible para filtros
            if self.config.use_heikin_ashi:
                # Usar Heikin Ashi si está habilitado
                ha_data = self.indicators.calculate_heiken_ashi(data)
                data['src'] = ha_data['close']
            else:
                data['src'] = data['close']

            # Calcular Heikin Ashi si está habilitado (para compatibilidad)
            if self.config.use_heikin_ashi:
                ha_data = self.indicators.calculate_heiken_ashi(data)
                data = pd.concat([data, ha_data], axis=1)

            # Calcular volumen promedio para filtros
            if 'volume' in data.columns:
                data['volume_avg'] = data['volume'].rolling(window=20).mean()

            return data

        except Exception as e:
            self.logger.error(f"Error calculando indicadores: {e}")
            return df

    def _apply_quality_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aplica filtros de calidad avanzados basados en las estrategias originales"""
        try:
            # Filtro de tendencia (de estrategia conservadora)
            if self.config.use_trend_filter and 'ema_200' in df.columns:
                if self.current_regime == MarketRegime.TRENDING_BULL:
                    trend_filter = df['src'] > df['ema_200'] * 0.99  # 1% por encima (más permisivo)
                elif self.current_regime == MarketRegime.TRENDING_BEAR:
                    trend_filter = df['src'] < df['ema_200'] * 1.01  # 1% por debajo (más permisivo)
                else:
                    trend_filter = True
                df['trend_filter'] = trend_filter
            else:
                df['trend_filter'] = True

            # Filtro de volatilidad (de estrategia conservadora)
            if self.config.use_volatility_filter and 'volatility' in df.columns and 'atr' in df.columns:
                # Filtro de ATR mínimo: ATR debe ser mayor que 50% del promedio
                atr_avg = df['atr'].rolling(window=10).mean()
                atr_filter = df['atr'] > (atr_avg * 0.5)
                df['atr_filter'] = atr_filter
            else:
                df['atr_filter'] = True

            # Filtro de volumen (de estrategia conservadora)
            if self.config.use_volume_filter and 'volume' in df.columns:
                volume_avg = df['volume'].rolling(window=20).mean()
                df['volume_filter'] = df['volume'] > (volume_avg * self.config.min_volume_multiplier)
            else:
                df['volume_filter'] = True

            # Filtro de régimen de mercado (de estrategia avanzada)
            if self.config.use_market_regime_filter:
                if self.current_regime in [MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR]:
                    regime_filter = True
                elif self.current_regime == MarketRegime.HIGH_VOLATILITY:
                    # En alta volatilidad, ser más conservador
                    regime_filter = False
                else:
                    regime_filter = True  # Permitir ranging con filtros adicionales
                df['regime_filter'] = regime_filter
            else:
                df['regime_filter'] = True

            # Filtro de momentum confluence (de estrategia avanzada)
            if self.config.use_momentum_confluence and 'adx' in df.columns:
                # ADX debe estar por encima del threshold para confirmar momentum
                momentum_filter = df['adx'] > self.config.adx_threshold
                df['momentum_filter'] = momentum_filter
            else:
                df['momentum_filter'] = True

            # Filtro anti-ruido para señales (de estrategia conservadora)
            if 'atr' in df.columns:
                # El cruce debe ser significativo (> 10% del ATR)
                if 'above' in df.columns:
                    cross_magnitude_above = abs(df['ema_val'] - df['xATRTrailingStop'])
                    noise_filter_above = cross_magnitude_above > (df['atr'] * 0.1)
                    df['noise_filter_above'] = noise_filter_above
                else:
                    df['noise_filter_above'] = True

                if 'below' in df.columns:
                    cross_magnitude_below = abs(df['xATRTrailingStop'] - df['ema_val'])
                    noise_filter_below = cross_magnitude_below > (df['atr'] * 0.1)
                    df['noise_filter_below'] = noise_filter_below
                else:
                    df['noise_filter_below'] = True
            else:
                df['noise_filter_above'] = True
                df['noise_filter_below'] = True

            # Combinar todos los filtros
            df['quality_filter'] = (
                df['trend_filter'] &
                df['atr_filter'] &
                df['volume_filter'] &
                df['regime_filter'] &
                df['momentum_filter'] &
                df['noise_filter_above'] &
                df['noise_filter_below']
            )

            return df

        except Exception as e:
            self.logger.error(f"Error aplicando filtros de calidad: {e}")
            df['quality_filter'] = True
            return df

    def _generate_ut_bot_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Genera señales UT Bot usando la lógica correcta del Pine Script original"""
        try:
            # Implementación fiel al Pine Script original de UT Bot + PSAR

            # ================= CÁLCULOS PRINCIPALES =================
            # Usar ATR del módulo de indicadores
            if 'atr' not in df.columns:
                df['atr'] = self.indicators.calculate_atr(df)

            # nLoss = sensitivity * ATR (parámetro 'a' en Pine Script)
            df['n_loss'] = self.config.sensitivity * df['atr']

            # Selección de fuente de precio (src) - ya creada en _calculate_all_indicators
            # Si no existe, usar close como fallback
            if 'src' not in df.columns:
                if self.config.use_heikin_ashi:
                    # Usar Heikin Ashi si está habilitado
                    ha_data = self.indicators.calculate_heiken_ashi(df)
                    df['src'] = ha_data['close']
                else:
                    df['src'] = df['close']

            # ================= PARABOLIC SAR =================
            # Usar SAR del módulo de indicadores
            if 'sar' not in df.columns:
                df['sar'] = self.indicators.calculate_sar(df)

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
            df['above'] = self._calculate_crossover(df['ema_val'], df['xATRTrailingStop'])

            # below = ta.crossover(xATRTrailingStop, ema_val)
            df['below'] = self._calculate_crossover(df['xATRTrailingStop'], df['ema_val'])

            # buy_signal = src > xATRTrailingStop and above
            df['buy_signal'] = (df['src'] > df['xATRTrailingStop']) & df['above']

            # sell_signal = src < xATRTrailingStop and below
            df['sell_signal'] = (df['src'] < df['xATRTrailingStop']) & df['below']

            # Aplicar filtros de calidad a las señales
            df['buy_signal'] = df['buy_signal'] & df['quality_filter']
            df['sell_signal'] = df['sell_signal'] & df['quality_filter']

            # Agregar alias para compatibilidad
            df['trailing_stop'] = df['xATRTrailingStop']

            return df

        except Exception as e:
            self.logger.error(f"Error generando señales UT Bot: {e}")
            df['buy_signal'] = False
            df['sell_signal'] = False
            return df

    def _calculate_crossover(self, series1: pd.Series, series2: pd.Series) -> pd.Series:
        """
        Implementa ta.crossover() de Pine Script
        Retorna True cuando series1 cruza por encima de series2
        """
        return (series1 > series2) & (series1.shift(1) <= series2.shift(1))

    def _calculate_crossunder(self, series1: pd.Series, series2: pd.Series) -> pd.Series:
        """
        Implementa ta.crossunder() de Pine Script
        Retorna True cuando series1 cruza por debajo de series2
        """
        return (series1 < series2) & (series1.shift(1) >= series2.shift(1))

    def _calculate_position_management(self, df: pd.DataFrame, signal_type: str, entry_price: float) -> Dict:
        """Calcula gestión de posición usando el módulo de riesgo"""
        try:
            # Usar el módulo de gestión de riesgo para calcular tamaño de posición
            atr_value = df['atr'].iloc[-1] if 'atr' in df.columns else 0

            if signal_type == 'buy':
                stop_loss = entry_price - (atr_value * self.config.stop_loss_atr_multiplier)
                take_profit = entry_price + (atr_value * self.config.take_profit_atr_multiplier)
            else:  # sell
                stop_loss = entry_price + (atr_value * self.config.stop_loss_atr_multiplier)
                take_profit = entry_price - (atr_value * self.config.take_profit_atr_multiplier)

            # Calcular tamaño de posición usando el risk manager
            position_size_result = self.risk_manager.calculate_position_size(
                symbol=self.current_symbol,
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                signal_strength=1.0,
                atr_value=atr_value
            )

            return {
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size_result.recommended_size if position_size_result else 0,
                'risk_amount': position_size_result.risk_amount if position_size_result else 0
            }

        except Exception as e:
            self.logger.error(f"Error calculando gestión de posición: {e}")
            return {
                'stop_loss': entry_price * 0.98,  # Stop loss por defecto
                'take_profit': entry_price * 1.06,  # Take profit por defecto
                'position_size': 0,
                'risk_amount': 0
            }

    def run(self, data: pd.DataFrame, symbol: str) -> Dict:
        """
        Ejecuta la estrategia unificada y devuelve resultados del backtesting

        Args:
            data: DataFrame con datos OHLCV
            symbol: Símbolo del activo

        Returns:
            Diccionario con resultados del backtesting
        """
        try:
            self.current_symbol = symbol

            # Paso 1: Detectar régimen de mercado
            self.current_regime = self._detect_market_regime(data)

            # Paso 2: Calcular todos los indicadores usando el módulo externo
            data_with_indicators = self._calculate_all_indicators(data)

            # Paso 3: Aplicar filtros de calidad
            data_filtered = self._apply_quality_filters(data_with_indicators)

            # Paso 4: Generar señales UT Bot
            data_with_signals = self._generate_ut_bot_signals(data_filtered)

            # Paso 5: Simular trading
            trades = []
            capital = 10000.0
            position = None

            for i in range(len(data_with_signals)):
                current_row = data_with_signals.iloc[i]
                current_price = current_row['close']

                # Verificar señales de entrada
                if position is None:
                    if current_row['buy_signal']:
                        # Abrir posición long
                        position = {
                            'type': 'long',
                            'entry_price': current_price,
                            'entry_time': current_row.name if hasattr(current_row, 'name') else i,
                            'position_size': 0,
                            'stop_loss': 0,
                            'take_profit': 0
                        }

                        # Calcular gestión de posición
                        position_mgmt = self._calculate_position_management(
                            data_with_signals.iloc[max(0, i-10):i+1], 'buy', current_price
                        )

                        position.update(position_mgmt)

                    elif current_row['sell_signal']:
                        # Abrir posición short
                        position = {
                            'type': 'short',
                            'entry_price': current_price,
                            'entry_time': current_row.name if hasattr(current_row, 'name') else i,
                            'position_size': 0,
                            'stop_loss': 0,
                            'take_profit': 0
                        }

                        # Calcular gestión de posición
                        position_mgmt = self._calculate_position_management(
                            data_with_signals.iloc[max(0, i-10):i+1], 'sell', current_price
                        )

                        position.update(position_mgmt)

                # Verificar condiciones de salida
                elif position is not None:
                    should_close = False
                    exit_reason = ""

                    if position['type'] == 'long':
                        if current_price >= position['take_profit']:
                            should_close = True
                            exit_reason = "take_profit"
                        elif current_price <= position['stop_loss']:
                            should_close = True
                            exit_reason = "stop_loss"
                    else:  # short
                        if current_price <= position['take_profit']:
                            should_close = True
                            exit_reason = "take_profit"
                        elif current_price >= position['stop_loss']:
                            should_close = True
                            exit_reason = "stop_loss"

                    if should_close:
                        # Calcular P&L
                        if position['type'] == 'long':
                            pnl = (current_price - position['entry_price']) * position['position_size']
                        else:
                            pnl = (position['entry_price'] - current_price) * position['position_size']

                        capital += pnl

                        trades.append({
                            'entry_price': position['entry_price'],
                            'exit_price': current_price,
                            'pnl': pnl,
                            'type': position['type'],
                            'exit_reason': exit_reason,
                            'entry_time': position['entry_time'],
                            'exit_time': current_row.name if hasattr(current_row, 'name') else i
                        })

                        position = None

            # Calcular métricas finales
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
                'sharpe_ratio': 0.0,  # Placeholder - se puede calcular con más datos
                'symbol': symbol,
                'trades': trades,
                'market_regime': self.current_regime.value,
                'trading_style': self.config.trading_style.value,
                'indicators_used': ['ATR', 'SAR', 'ADX', 'EMA_10', 'EMA_20', 'EMA_200', 'Volatility'],
                'filters_applied': ['trend', 'volatility', 'volume', 'regime', 'momentum'] if self.config.use_trend_filter else []
            }

        except Exception as e:
            self.logger.error(f"Error ejecutando estrategia unificada: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'symbol': symbol,
                'trades': [],
                'market_regime': 'unknown',
                'trading_style': self.config.trading_style.value,
                'indicators_used': [],
                'filters_applied': []
            }

    def analyze_latest(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """
        Analiza la última vela y devuelve una oportunidad de trading (paper/live).

        Retorna:
        - signal: "buy" | "sell" | None
        - score: 0..1
        - stop_loss / take_profit / position_size sugeridos (si hay señal)
        """
        self.current_symbol = symbol
        self.current_regime = self._detect_market_regime(data)

        data_with_indicators = self._calculate_all_indicators(data)
        data_filtered = self._apply_quality_filters(data_with_indicators)
        data_with_signals = self._generate_ut_bot_signals(data_filtered)

        last = data_with_signals.iloc[-1]
        signal: Optional[str] = None
        if bool(last.get("buy_signal", False)):
            signal = "buy"
        elif bool(last.get("sell_signal", False)):
            signal = "sell"

        adx = float(last.get("adx", 0.0) or 0.0)
        volatility = float(last.get("volatility", 0.0) or 0.0)
        quality = bool(last.get("quality_filter", False))

        score = 0.0
        reasons: list[str] = []

        if signal:
            score += 0.55
            reasons.append(f"signal={signal}")
        if quality:
            score += 0.15
            reasons.append("quality_filter=pass")

        adx_threshold = float(getattr(self.config, "adx_threshold", 25.0) or 25.0)
        adx_component = min(adx / max(adx_threshold, 1.0), 2.0) / 2.0
        score += 0.2 * adx_component
        reasons.append(f"adx={adx:.2f}")

        if volatility > 0.08:
            score -= 0.1
            reasons.append(f"high_volatility={volatility:.4f}")
        else:
            score += 0.05
            reasons.append(f"volatility={volatility:.4f}")

        regime = self.current_regime.value if hasattr(self.current_regime, "value") else str(self.current_regime)
        if "trending" in regime:
            score += 0.05
            reasons.append(f"regime={regime}")

        score = max(0.0, min(1.0, score))

        position_mgmt: Dict[str, Any] = {}
        if signal:
            price = float(last["close"])
            position_mgmt = self._calculate_position_management(
                data_with_signals.iloc[max(0, len(data_with_signals) - 20):], signal, price
            )

        ts = last.name if hasattr(last, "name") else None
        return {
            "symbol": symbol,
            "timestamp": ts,
            "regime": regime,
            "signal": signal,
            "score": score,
            "reasons": reasons,
            "price": float(last["close"]),
            **position_mgmt,
        }

    def get_strategy_info(self) -> Dict:
        """Retorna información detallada sobre la estrategia unificada"""
        return {
            'name': 'Estrategia Unificada UT Bot + PSAR',
            'version': '1.0',
            'description': 'Estrategia que combina las mejores características de todas las estrategias existentes',
            'trading_style': self.config.trading_style.value,
            'features': {
                'indicators_module': 'Usa módulo externo de indicadores técnicos',
                'risk_management': 'Usa módulo externo de gestión de riesgo',
                'market_regime_detection': self.config.use_market_regime_filter,
                'quality_filters': {
                    'trend_filter': self.config.use_trend_filter,
                    'volatility_filter': self.config.use_volatility_filter,
                    'volume_filter': self.config.use_volume_filter,
                    'momentum_confluence': self.config.use_momentum_confluence
                },
                'compensation_system': self.config.compensation_enabled
            },
            'parameters': {
                'sensitivity': self.config.sensitivity,
                'atr_period': self.config.atr_period,
                'risk_per_trade': self.config.risk_per_trade,
                'stop_loss_atr_multiplier': self.config.stop_loss_atr_multiplier,
                'take_profit_atr_multiplier': self.config.take_profit_atr_multiplier,
                'psar_acceleration': self.config.psar_acceleration,
                'psar_maximum': self.config.psar_maximum
            },
            'supported_symbols': list(self.config.symbol_configs.keys()) if self.config.symbol_configs else 'all'
        }


# Funciones de fábrica para crear estrategias con diferentes estilos
def create_conservative_strategy(symbol_configs: Dict = None) -> UnifiedUTBotPSARStrategy:
    """Crea una estrategia con configuración conservadora"""
    config = UnifiedStrategyConfig(
        trading_style=TradingStyle.CONSERVATIVE,
        symbol_configs=symbol_configs or {}
    )
    return UnifiedUTBotPSARStrategy(config)


def create_moderate_strategy(symbol_configs: Dict = None) -> UnifiedUTBotPSARStrategy:
    """Crea una estrategia con configuración moderada"""
    config = UnifiedStrategyConfig(
        trading_style=TradingStyle.MODERATE,
        symbol_configs=symbol_configs or {}
    )
    return UnifiedUTBotPSARStrategy(config)


def create_aggressive_strategy(symbol_configs: Dict = None) -> UnifiedUTBotPSARStrategy:
    """Crea una estrategia con configuración agresiva"""
    config = UnifiedStrategyConfig(
        trading_style=TradingStyle.AGGRESSIVE,
        symbol_configs=symbol_configs or {}
    )
    return UnifiedUTBotPSARStrategy(config)


def create_ultra_aggressive_strategy(symbol_configs: Dict = None) -> UnifiedUTBotPSARStrategy:
    """Crea una estrategia con configuración ultra agresiva"""
    config = UnifiedStrategyConfig(
        trading_style=TradingStyle.ULTRA_AGGRESSIVE,
        symbol_configs=symbol_configs or {}
    )
    return UnifiedUTBotPSARStrategy(config)
