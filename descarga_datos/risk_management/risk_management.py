"""
MÓDULO DE GESTIÓN DE RIESGO
===========================

Sistema avanzado de gestión de riesgo para trading cuantitativo.
Responsabilidades:
- Cálculo de tamaños de posición
- Gestión de stop loss y take profit dinámicos
- Monitoreo de drawdown en tiempo real
- Implementación de Kelly Criterion
- Gestión de correlaciones entre posiciones
- Límites de exposición por sector/activo
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from enum import Enum
import math

from config.config import Config
from utils.logger import setup_logging

# Configurar logging
logger = logging.getLogger(__name__)

@dataclass
class RiskConfig:
    """Configuración de riesgo básica"""
    max_drawdown: float = 0.15  # 15% máximo drawdown
    max_positions: int = 10
    max_exposure_per_position: float = 0.1  # 10% por posición
    initial_capital: float = 10000.0
    risk_per_trade: float = 0.02  # 2% por trade
    max_correlation: float = 0.7
    stop_loss_atr_multiplier: float = 1.5
    take_profit_atr_multiplier: float = 3.0
    trailing_stop_activation: float = 0.01  # 1% para activar trailing stop
    kelly_fraction: float = 0.1  # 10% fracción de Kelly por defecto

    # Configuración del sistema de compensación
    compensation_enabled: bool = True
    compensation_threshold: float = 0.03  # 3% de pérdida para activar compensación
    compensation_max_size: float = 0.5  # Máximo 50% del tamaño de la posición principal
    compensation_risk_multiplier: float = 1.5  # Multiplicador de riesgo para compensación
    compensation_take_profit_multiplier: float = 2.0  # Multiplicador TP para compensación
    max_compensation_positions: int = 1  # Máximo 1 posición de compensación por principal

class PositionSizeMethod(Enum):
    FIXED = "fixed"
    KELLY = "kelly"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    RISK_PARITY = "risk_parity"

class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    ULTRA_AGGRESSIVE = "ultra_aggressive"

class AlertType(Enum):
    """Tipos de alertas del sistema de riesgo"""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    DRAWDOWN_WARNING = "drawdown_warning"
    CORRELATION_ALERT = "correlation_alert"
    CIRCUIT_BREAKER = "circuit_breaker"
    KELLY_ADJUSTMENT = "kelly_adjustment"
    TRAILING_STOP_HIT = "trailing_stop_hit"
    MAX_EXPOSURE_EXCEEDED = "max_exposure_exceeded"
    COMPENSATION_TRIGGERED = "compensation_triggered"
    COMPENSATION_CLOSED = "compensation_closed"
    REVERSAL_DETECTED = "reversal_detected"

@dataclass
class Position:
    """Representa una posición de trading"""
    symbol: str
    entry_price: float
    quantity: float
    entry_time: datetime
    position_type: str  # 'long' or 'short'
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_unrealized_pnl: float = 0.0
    max_drawdown: float = 0.0
    risk_amount: float = 0.0
    kelly_size: float = 0.0
    entry_signal_strength: float = 0.0
    entry_confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    trailing_stop: Optional[float] = None

@dataclass
class CompensationPosition:
    """Representa una posición de compensación"""
    symbol: str
    parent_position_id: str  # ID de la posición principal que compensa
    entry_price: float
    quantity: float
    entry_time: datetime
    position_type: str  # 'long' or 'short' (opuesto a la principal)
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    target_compensation_amount: float = 0.0  # Cantidad a compensar
    compensation_achieved: float = 0.0  # Compensación lograda hasta ahora
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskMetrics:
    """Métricas de riesgo del portfolio"""
    total_risk: float
    var_95: float  # Value at Risk 95%
    expected_shortfall: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    correlation_risk: float
    sector_concentration: Dict[str, float]
    daily_var: float
    portfolio_volatility: float
    risk_adjusted_return: float

@dataclass
class PositionSizeResult:
    """Resultado del cálculo de tamaño de posición"""
    recommended_size: float
    max_position_value: float
    risk_amount: float
    stop_loss_price: float
    take_profit_price: float
    position_risk_percent: float
    confidence_score: float
    warnings: List[str] = field(default_factory=list)

class AdvancedRiskManager:
    """Gestor avanzado de riesgo para trading cuantitativo"""
    
    def __init__(self, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.risk_config = RiskConfig()  # Usar configuración básica por defecto
        
        # Estado del portfolio
        self.portfolio_value = self.risk_config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        self.daily_returns: List[float] = []
        self.equity_curve: List[float] = [self.portfolio_value]
        
        # Métricas de riesgo
        self.current_drawdown = 0.0
        self.max_drawdown_reached = 0.0
        self.peak_equity = self.portfolio_value
        
        # Límites y restricciones
        self.max_positions = 10
        self.max_sector_exposure = 0.3  # 30% máximo por sector
        self.correlation_threshold = 0.7
        
        # Sistema de compensación
        self.compensation_positions: Dict[str, CompensationPosition] = {}
        self.reversal_detection_enabled = True
        self.compensation_pairs: Dict[str, str] = {}  # position_id -> compensation_id
        
        self.logger.info("[OK] Advanced Risk Manager inicializado")
    
    def set_config_manager(self, config_manager):
        """Configura el gestor de configuración"""
        self.config_manager = config_manager
        self.logger.info("[OK] Config manager configurado en Risk Manager")

    def _get_symbol_config_safe(self, symbol: str) -> Dict[str, Any]:
        """
        Obtiene configuración por símbolo sin depender de config_manager.

        El motor de ejecución/paper puede usar RiskManager sin un ConfigManager,
        así que este método evita AttributeError y provee defaults coherentes.
        """
        if self.config_manager is None:
            return {
                'max_position_size': 10.0,  # %
                'min_position_size': 10.0,
                'leverage': 1.0
            }
        cfg = self.config_manager.get_symbol_config(symbol)
        return cfg or {}
    
    def calculate_position_size(self, symbol: str, entry_price: float, 
                              stop_loss_price: float, signal_strength: float = 1.0,
                              atr_value: Optional[float] = None) -> PositionSizeResult:
        """Calcula el tamaño óptimo de posición usando múltiples métodos"""
        try:
            # Si no hay config_manager, usar configuración básica
            if self.config_manager is None:
                symbol_config = {
                    # Porcentaje máximo del portfolio (ej: 10 = 10%)
                    'max_position_size': 10.0,
                    'min_position_size': 10.0,
                    'leverage': 1.0
                }
            else:
                symbol_config = self.config_manager.get_symbol_config(symbol)
                if not symbol_config:
                    return self._create_zero_position_result("Símbolo no configurado")
            
            # Validaciones iniciales
            if entry_price <= 0 or stop_loss_price <= 0:
                return self._create_zero_position_result("Precios inválidos")
            
            if abs(entry_price - stop_loss_price) / entry_price < 0.005:  # Menos de 0.5%
                return self._create_zero_position_result("Stop loss muy cercano")
            
            # Verificar límites de drawdown
            if self.current_drawdown > self.risk_config.max_drawdown:
                return self._create_zero_position_result("Límite de drawdown excedido")
            
            # Calcular riesgo por trade
            risk_per_trade = self.portfolio_value * self.risk_config.risk_per_trade
            
            # Calcular tamaño base
            price_risk = abs(entry_price - stop_loss_price)
            base_position_size = risk_per_trade / price_risk
            
            # Aplicar diferentes métodos de sizing
            kelly_size = self._calculate_kelly_position_size(symbol, signal_strength)
            volatility_size = self._calculate_volatility_adjusted_size(
                symbol, entry_price, atr_value
            )
            
            # Combinar métodos
            recommended_sizes = [base_position_size, kelly_size, volatility_size]
            recommended_sizes = [size for size in recommended_sizes if size > 0]
            
            if not recommended_sizes:
                return self._create_zero_position_result("No se puede determinar tamaño")
            
            # Usar el mínimo para ser conservador
            final_size = min(recommended_sizes)
            
            # Aplicar límites adicionales
            max_position_pct = symbol_config.get('max_position_size', 1000.0) / 100.0  # Convertir a porcentaje
            max_position_value = self.portfolio_value * max_position_pct
            max_size_by_value = max_position_value / entry_price
            final_size = min(final_size, max_size_by_value)
            
            # Verificar límite mínimo
            min_position_value = 100  # $100 mínimo
            if final_size * entry_price < min_position_value:
                return self._create_zero_position_result("Posición muy pequeña")
            
            # Calcular take profit dinámico
            take_profit_price = self._calculate_dynamic_take_profit(
                entry_price, stop_loss_price, atr_value, signal_strength
            )
            
            # Calcular métricas finales
            position_value = final_size * entry_price
            risk_amount = final_size * price_risk
            position_risk_percent = (risk_amount / self.portfolio_value) * 100
            
            # Calcular confianza
            confidence_score = self._calculate_position_confidence(
                symbol, signal_strength, position_risk_percent
            )
            
            # Generar warnings
            warnings = self._generate_position_warnings(
                symbol, position_value, position_risk_percent
            )
            
            return PositionSizeResult(
                recommended_size=final_size,
                max_position_value=position_value,
                risk_amount=risk_amount,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_risk_percent=position_risk_percent,
                confidence_score=confidence_score,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error calculando tamaño de posición: {e}")
            return self._create_zero_position_result(f"Error: {str(e)}")
    
    def _calculate_kelly_position_size(self, symbol: str, signal_strength: float) -> float:
        """Calcula tamaño usando Kelly Criterion"""
        try:
            # Obtener historial de trades para este símbolo
            symbol_trades = [t for t in self.trade_history if t.get('symbol') == symbol]
            
            if len(symbol_trades) < 10:  # Necesitamos historial mínimo
                # Usar parámetros conservadores por defecto
                win_rate = 0.6
                avg_win = 1.5
                avg_loss = 1.0
            else:
                wins = [t['return_pct'] for t in symbol_trades if t['return_pct'] > 0]
                losses = [t['return_pct'] for t in symbol_trades if t['return_pct'] < 0]
                
                win_rate = len(wins) / len(symbol_trades)
                avg_win = np.mean(wins) if wins else 1.5
                avg_loss = abs(np.mean(losses)) if losses else 1.0
            
            # Fórmula de Kelly: f = (bp - q) / b
            # donde b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - win_rate
            
            kelly_fraction = (b * p - q) / b
            
            # Aplicar limitaciones conservadoras
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Máximo 25%
            
            # Ajustar por fuerza de señal
            adjusted_fraction = kelly_fraction * signal_strength * self.risk_config.kelly_fraction
            
            # Convertir fracción a tamaño de posición
            max_position_value = self.portfolio_value * adjusted_fraction
            
            return max_position_value  # Retornar valor, no cantidad
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error en Kelly sizing: {e}")
            return 0.0
    
    def _calculate_volatility_adjusted_size(self, symbol: str, entry_price: float,
                                          atr_value: Optional[float]) -> float:
        """Calcula tamaño ajustado por volatilidad"""
        try:
            if not atr_value or atr_value <= 0:
                # Usar volatilidad estimada si no hay ATR
                estimated_volatility = entry_price * 0.02  # 2% diario estimado
            else:
                estimated_volatility = atr_value
            
            # Normalizar volatilidad (objetivo: 1% de volatilidad diaria)
            target_volatility = entry_price * 0.01
            volatility_adjustment = target_volatility / estimated_volatility
            
            # Limitar el ajuste
            volatility_adjustment = max(0.1, min(volatility_adjustment, 3.0))
            
            # Calcular tamaño base
            base_risk = self.portfolio_value * self.risk_config.risk_per_trade
            
            # Ajustar por volatilidad
            adjusted_size = (base_risk * volatility_adjustment) / entry_price
            
            return adjusted_size
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error en volatility sizing: {e}")
            return 0.0
    
    def _calculate_dynamic_take_profit(self, entry_price: float, stop_loss_price: float,
                                     atr_value: Optional[float], signal_strength: float) -> float:
        """Calcula take profit dinámico"""
        try:
            # Distancia del stop loss
            stop_distance = abs(entry_price - stop_loss_price)
            
            # Base ratio (risk:reward)
            base_ratio = 2.0  # 1:2 por defecto
            
            # Ajustar ratio por fuerza de señal
            if signal_strength > 0.8:
                ratio = 2.5
            elif signal_strength > 0.6:
                ratio = 2.0
            else:
                ratio = 1.5
            
            # Ajustar por ATR si está disponible
            if atr_value and atr_value > 0:
                # Si ATR sugiere más volatilidad, expandir target
                atr_ratio = atr_value / stop_distance
                if atr_ratio > 1.5:
                    ratio *= 1.2
                elif atr_ratio < 0.5:
                    ratio *= 0.8
            
            # Calcular take profit
            if entry_price > stop_loss_price:  # Long position
                take_profit = entry_price + (stop_distance * ratio)
            else:  # Short position
                take_profit = entry_price - (stop_distance * ratio)
            
            return take_profit
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error calculando take profit: {e}")
            return entry_price * 1.02  # 2% por defecto
    
    def _calculate_position_confidence(self, symbol: str, signal_strength: float,
                                     position_risk_percent: float) -> float:
        """Calcula score de confianza para la posición"""
        try:
            confidence = 0.5  # Base
            
            # Ajuste por fuerza de señal
            confidence += (signal_strength - 0.5) * 0.3
            
            # Ajuste por riesgo de posición
            if position_risk_percent < 1.0:
                confidence += 0.1
            elif position_risk_percent > 3.0:
                confidence -= 0.2
            
            # Ajuste por drawdown actual
            if self.current_drawdown < 0.02:  # Menos del 2%
                confidence += 0.1
            elif self.current_drawdown > 0.05:  # Más del 5%
                confidence -= 0.2
            
            # Ajuste por número de posiciones abiertas
            open_positions = len(self.positions)
            if open_positions < 3:
                confidence += 0.05
            elif open_positions > 7:
                confidence -= 0.1
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error calculando confianza: {e}")
            return 0.5
    
    def _generate_position_warnings(self, symbol: str, position_value: float,
                                  position_risk_percent: float) -> List[str]:
        """Genera warnings para la posición"""
        warnings = []
        
        # Warning por tamaño de posición
        if position_risk_percent > 2.5:
            warnings.append(f"Alto riesgo: {position_risk_percent:.1f}% del portfolio")
        
        # Warning por concentración
        symbol_config = self._get_symbol_config_safe(symbol)
        if symbol_config and position_value > self.portfolio_value * 0.25:
            warnings.append("Alta concentración en un solo activo")
        
        # Warning por drawdown
        if self.current_drawdown > 0.05:
            warnings.append(f"Portfolio en drawdown: {self.current_drawdown*100:.1f}%")
        
        # Warning por número de posiciones
        if len(self.positions) >= self.max_positions:
            warnings.append("Límite máximo de posiciones alcanzado")
        
        return warnings
    
    def _create_zero_position_result(self, reason: str) -> PositionSizeResult:
        """Crea resultado con posición cero"""
        return PositionSizeResult(
            recommended_size=0.0,
            max_position_value=0.0,
            risk_amount=0.0,
            stop_loss_price=0.0,
            take_profit_price=0.0,
            position_risk_percent=0.0,
            confidence_score=0.0,
            warnings=[reason]
        )
    
    def open_position(self, symbol: str, entry_price: float, quantity: float,
                     position_type: str, stop_loss: float, take_profit: float,
                     risk_amount: float) -> bool:
        """Abre una nueva posición"""
        try:
            if symbol in self.positions:
                self.logger.warning(f"[WARNING] Posición ya existe para {symbol}")
                return False
            
            position = Position(
                symbol=symbol,
                entry_price=entry_price,
                quantity=quantity,
                entry_time=datetime.now(),
                position_type=position_type,
                stop_loss=stop_loss,
                take_profit=take_profit,
                current_price=entry_price,
                risk_amount=risk_amount
            )
            
            self.positions[symbol] = position
            self.logger.info(f"[OK] Posición abierta: {symbol} {quantity} @ {entry_price}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error abriendo posición: {e}")
            return False
    
    def update_position(self, symbol: str, current_price: float, update_trailing_stop: bool = True) -> None:
        """Actualiza una posición existente con soporte para trailing stop"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # Calcular PnL
        if position.position_type == 'long':
            pnl = (current_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - current_price) * position.quantity
        
        position.unrealized_pnl = pnl
        
        # Actualizar máximo PnL y drawdown de la posición
        if pnl > position.max_unrealized_pnl:
            position.max_unrealized_pnl = pnl
        
        if position.max_unrealized_pnl > 0:
            position.max_drawdown = max(
                position.max_drawdown,
                (position.max_unrealized_pnl - pnl) / position.max_unrealized_pnl
            )
            
        # Actualizar trailing stop si está habilitado
        if update_trailing_stop and position.trailing_stop is not None:
            # Actualizar trailing stop basado en el precio actual
            if position.position_type == 'long':
                # Para posiciones largas, el trailing stop solo puede subir
                if position.trailing_stop is None:
                    # Inicializar el trailing stop si no existe
                    trail_distance = abs(position.entry_price - position.stop_loss)
                    position.trailing_stop = max(position.stop_loss, current_price - trail_distance)
                else:
                    # Calculamos un nuevo stop basado en el precio actual
                    trail_distance = abs(position.entry_price - position.stop_loss)
                    new_stop = current_price - trail_distance
                    
                    # Solo actualizamos si el nuevo stop es mayor que el actual
                    if new_stop > position.trailing_stop:
                        old_stop = position.trailing_stop
                        position.trailing_stop = new_stop
                        position.stop_loss = new_stop  # Actualizamos también el stop loss regular
                        logger.info(f"Trailing stop actualizado para {symbol}: {old_stop:.4f} -> {new_stop:.4f}")
            else:
                # Para posiciones cortas, el trailing stop solo puede bajar
                if position.trailing_stop is None:
                    # Inicializar el trailing stop si no existe
                    trail_distance = abs(position.entry_price - position.stop_loss)
                    position.trailing_stop = min(position.stop_loss, current_price + trail_distance)
                else:
                    # Calculamos un nuevo stop basado en el precio actual
                    trail_distance = abs(position.entry_price - position.stop_loss)
                    new_stop = current_price + trail_distance
                    
                    # Solo actualizamos si el nuevo stop es menor que el actual
                    if new_stop < position.trailing_stop:
                        old_stop = position.trailing_stop
                        position.trailing_stop = new_stop
                        position.stop_loss = new_stop  # Actualizamos también el stop loss regular
                        logger.info(f"Trailing stop actualizado para {symbol}: {old_stop:.4f} -> {new_stop:.4f}")
    
    def close_position(self, symbol: str, exit_price: float, exit_reason: str) -> Optional[Dict]:
        """Cierra una posición"""
        if symbol not in self.positions:
            self.logger.warning(f"[WARNING] No existe posición para {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Calcular PnL realizado
        if position.position_type == 'long':
            realized_pnl = (exit_price - position.entry_price) * position.quantity
        else:
            realized_pnl = (position.entry_price - exit_price) * position.quantity
        
        # Crear registro del trade
        trade_record = {
            'symbol': symbol,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'quantity': position.quantity,
            'position_type': position.position_type,
            'entry_time': position.entry_time,
            'exit_time': datetime.now(),
            'realized_pnl': realized_pnl,
            'return_pct': (realized_pnl / (position.entry_price * position.quantity)) * 100,
            'exit_reason': exit_reason,
            'risk_amount': position.risk_amount,
            'max_drawdown': position.max_drawdown
        }
        
        # Actualizar portfolio
        self.portfolio_value += realized_pnl
        self.trade_history.append(trade_record)
        
        # Eliminar posición
        del self.positions[symbol]
        
        self.logger.info(f"[OK] Posición cerrada: {symbol} PnL: ${realized_pnl:.2f}")
        
        return trade_record
    
    def check_stop_loss_take_profit(self) -> List[str]:
        """Verifica stops, targets y trailing stops para todas las posiciones"""
        positions_to_close = []
        
        for symbol, position in self.positions.items():
            current_price = position.current_price
            
            # Determinar qué stop loss usar (trailing stop o stop loss normal)
            effective_stop = position.trailing_stop if position.trailing_stop is not None else position.stop_loss
            
            if position.position_type == 'long':
                if current_price <= effective_stop:
                    reason = "Trailing Stop" if position.trailing_stop is not None and position.trailing_stop == effective_stop else "Stop Loss"
                    positions_to_close.append((symbol, current_price, reason))
                elif current_price >= position.take_profit:
                    positions_to_close.append((symbol, current_price, "Take Profit"))
            
            else:  # short position
                if current_price >= effective_stop:
                    reason = "Trailing Stop" if position.trailing_stop is not None and position.trailing_stop == effective_stop else "Stop Loss"
                    positions_to_close.append((symbol, current_price, reason))
                elif current_price <= position.take_profit:
                    positions_to_close.append((symbol, current_price, "Take Profit"))
        
        # Cerrar posiciones que han alcanzado stops/targets
        closed_positions = []
        for symbol, price, reason in positions_to_close:
            trade_record = self.close_position(symbol, price, reason)
            if trade_record:
                closed_positions.append(symbol)
                # Registrar el tipo de alerta
                alert_type = AlertType.TRAILING_STOP_HIT if "Trailing" in reason else \
                             AlertType.STOP_LOSS if "Stop Loss" in reason else \
                             AlertType.TAKE_PROFIT
                self._trigger_alert(alert_type, f"Cierre de posición: {symbol}", 
                                  {"symbol": symbol, "price": price, "reason": reason})
        
        return closed_positions
    
    def _trigger_alert(self, alert_type: AlertType, message: str, data: Dict[str, Any] = None) -> None:
        """
        Genera una alerta en el sistema de gestión de riesgo
        
        Args:
            alert_type: Tipo de alerta del sistema
            message: Mensaje descriptivo
            data: Datos adicionales relevantes para la alerta
        """
        if data is None:
            data = {}
            
        alert = {
            'type': alert_type.value,
            'message': message,
            'timestamp': datetime.now(),
            'data': data
        }
        
        # Determinar nivel de severidad según tipo de alerta
        log_level = logging.WARNING
        if alert_type in [AlertType.CIRCUIT_BREAKER, AlertType.DRAWDOWN_WARNING]:
            log_level = logging.ERROR
        elif alert_type in [AlertType.STOP_LOSS, AlertType.TRAILING_STOP_HIT]:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Loguear la alerta
        self.logger.log(log_level, f"ALERTA {alert_type.value}: {message}")
        
        # Acciones específicas según tipo de alerta
        if alert_type == AlertType.DRAWDOWN_WARNING:
            if data.get('drawdown', 0) > self.risk_config.max_drawdown:
                self.logger.error(f"EMERGENCIA: Drawdown critico detectado: {data.get('drawdown', 0):.2%}")
    
    # === SISTEMA DE COMPENSACIÓN DE OPERACIONES ===
    
    def check_compensation_opportunities(self) -> List[str]:
        """
        Verifica si alguna posición necesita compensación por reversión
        
        Returns:
            Lista de símbolos que activaron compensación
        """
        if not self.risk_config.compensation_enabled:
            return []
        
        compensation_triggers = []
        
        for symbol, position in self.positions.items():
            # Solo procesar si no tiene compensación activa
            if symbol in self.compensation_pairs:
                continue
                
            # Verificar si la posición está en pérdida y supera el umbral
            if self._should_trigger_compensation(position):
                if self._create_compensation_position(symbol, position):
                    compensation_triggers.append(symbol)
                    self._trigger_alert(
                        AlertType.COMPENSATION_TRIGGERED,
                        f"Compensación activada para {symbol}",
                        {
                            'symbol': symbol,
                            'position_type': position.position_type,
                            'current_pnl': position.unrealized_pnl,
                            'threshold': self.risk_config.compensation_threshold
                        }
                    )
        
        return compensation_triggers
    
    def _should_trigger_compensation(self, position: Position) -> bool:
        """
        Determina si una posición debe activar compensación
        
        Args:
            position: Posición a evaluar
            
        Returns:
            True si debe activar compensación
        """
        # Verificar que esté en pérdida
        if position.unrealized_pnl >= 0:
            return False
        
        # Calcular pérdida porcentual
        loss_percentage = abs(position.unrealized_pnl) / (position.entry_price * position.quantity)
        
        # Verificar umbral de activación
        if loss_percentage < self.risk_config.compensation_threshold:
            return False
        
        # Verificar que no haya una compensación activa
        if position.symbol in self.compensation_pairs:
            return False
        
        # Verificar límite de posiciones de compensación
        active_compensations = len(self.compensation_positions)
        if active_compensations >= self.risk_config.max_compensation_positions:
            return False
        
        return True
    
    def _create_compensation_position(self, symbol: str, parent_position: Position) -> bool:
        """
        Crea una posición de compensación para la posición principal
        
        Args:
            symbol: Símbolo de la posición
            parent_position: Posición principal a compensar
            
        Returns:
            True si se creó exitosamente
        """
        try:
            # Determinar tipo de compensación (opuesto a la principal)
            compensation_type = 'short' if parent_position.position_type == 'long' else 'long'
            
            # Calcular tamaño de compensación (porcentaje de la posición principal)
            compensation_size = parent_position.quantity * self.risk_config.compensation_max_size
            
            # Calcular precio de entrada para compensación
            current_price = parent_position.current_price
            
            # Calcular stop loss y take profit para compensación
            risk_distance = abs(parent_position.entry_price - parent_position.stop_loss)
            compensation_risk_distance = risk_distance * self.risk_config.compensation_risk_multiplier
            
            if compensation_type == 'long':
                compensation_stop = current_price - compensation_risk_distance
                compensation_target = current_price + (compensation_risk_distance * self.risk_config.compensation_take_profit_multiplier)
            else:
                compensation_stop = current_price + compensation_risk_distance
                compensation_target = current_price - (compensation_risk_distance * self.risk_config.compensation_take_profit_multiplier)
            
            # Calcular cantidad a compensar (pérdida actual de la posición principal)
            target_compensation = abs(parent_position.unrealized_pnl)
            
            # Crear ID único para la compensación
            compensation_id = f"{symbol}_comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Crear posición de compensación
            compensation_position = CompensationPosition(
                symbol=symbol,
                parent_position_id=symbol,  # Usar el symbol como ID de la posición principal
                entry_price=current_price,
                quantity=compensation_size,
                entry_time=datetime.now(),
                position_type=compensation_type,
                stop_loss=compensation_stop,
                take_profit=compensation_target,
                current_price=current_price,
                target_compensation_amount=target_compensation,
                metadata={
                    'compensation_reason': 'reversal_loss_compensation',
                    'parent_position_type': parent_position.position_type,
                    'trigger_threshold': self.risk_config.compensation_threshold,
                    'loss_at_trigger': parent_position.unrealized_pnl
                }
            )
            
            # Registrar la compensación
            self.compensation_positions[compensation_id] = compensation_position
            self.compensation_pairs[symbol] = compensation_id
            
            self.logger.info(f"[COMPENSATION] Posición de compensación creada: {compensation_id}")
            self.logger.info(f"[COMPENSATION] Tipo: {compensation_type}, Tamaño: {compensation_size}")
            self.logger.info(f"[COMPENSATION] Objetivo de compensación: ${target_compensation:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error creando compensación para {symbol}: {e}")
            return False
    
    def update_compensation_positions(self) -> List[str]:
        """
        Actualiza todas las posiciones de compensación y verifica cierres
        
        Returns:
            Lista de IDs de compensaciones cerradas
        """
        closed_compensations = []
        
        for comp_id, compensation in list(self.compensation_positions.items()):
            # Actualizar precio actual
            if compensation.symbol in self.positions:
                parent_position = self.positions[compensation.symbol]
                compensation.current_price = parent_position.current_price
                
                # Calcular PnL de la compensación
                if compensation.position_type == 'long':
                    compensation.unrealized_pnl = (compensation.current_price - compensation.entry_price) * compensation.quantity
                else:
                    compensation.unrealized_pnl = (compensation.entry_price - compensation.current_price) * compensation.quantity
                
                # Verificar si se alcanzó el objetivo de compensación
                if self._check_compensation_target_achieved(compensation, parent_position):
                    closed_compensations.append(comp_id)
                    self._close_compensation_pair(comp_id, compensation, parent_position, "compensation_target_achieved")
                
                # Verificar stops de compensación
                elif self._check_compensation_stops(compensation):
                    closed_compensations.append(comp_id)
                    self._close_compensation_pair(comp_id, compensation, parent_position, "compensation_stop_hit")
        
        return closed_compensations
    
    def _check_compensation_target_achieved(self, compensation: CompensationPosition, 
                                          parent_position: Position) -> bool:
        """
        Verifica si se ha alcanzado el objetivo de compensación
        
        Args:
            compensation: Posición de compensación
            parent_position: Posición principal
            
        Returns:
            True si se debe cerrar la pareja
        """
        # Calcular pérdida total combinada
        total_combined_loss = parent_position.unrealized_pnl + compensation.unrealized_pnl
        
        # Si las pérdidas se han compensado (total cercano a cero o positivo)
        if total_combined_loss >= -1.0:  # Tolerancia de $1
            compensation.compensation_achieved = abs(parent_position.unrealized_pnl)
            return True
        
        return False
    
    def _check_compensation_stops(self, compensation: CompensationPosition) -> bool:
        """
        Verifica si la compensación alcanzó sus stops
        
        Args:
            compensation: Posición de compensación
            
        Returns:
            True si debe cerrarse por stop
        """
        if compensation.position_type == 'long':
            return compensation.current_price <= compensation.stop_loss
        else:
            return compensation.current_price >= compensation.stop_loss
    
    def _close_compensation_pair(self, compensation_id: str, 
                               compensation: CompensationPosition,
                               parent_position: Position, 
                               reason: str) -> None:
        """
        Cierra una pareja de posiciones (principal + compensación)
        
        Args:
            compensation_id: ID de la compensación
            compensation: Posición de compensación
            parent_position: Posición principal
            reason: Razón del cierre
        """
        try:
            symbol = compensation.symbol
            
            # Cerrar posición principal
            parent_trade = self.close_position(symbol, parent_position.current_price, 
                                             f"Compensation: {reason}")
            
            # Cerrar posición de compensación
            compensation_trade = self._close_compensation_position(compensation_id, 
                                                                 compensation.current_price,
                                                                 reason)
            
            # Calcular resultado neto
            total_pnl = (parent_trade['realized_pnl'] if parent_trade else 0) + \
                       (compensation_trade['realized_pnl'] if compensation_trade else 0)
            
            # Limpiar registros
            if symbol in self.compensation_pairs:
                del self.compensation_pairs[symbol]
            
            if compensation_id in self.compensation_positions:
                del self.compensation_positions[compensation_id]
            
            self.logger.info(f"[COMPENSATION] Pareja cerrada: {symbol}")
            self.logger.info(f"[COMPENSATION] PnL Principal: ${parent_trade['realized_pnl']:.2f}" if parent_trade else "[COMPENSATION] Error cerrando principal")
            self.logger.info(f"[COMPENSATION] PnL Compensación: ${compensation_trade['realized_pnl']:.2f}" if compensation_trade else "[COMPENSATION] Error cerrando compensación")
            self.logger.info(f"[COMPENSATION] PnL Total: ${total_pnl:.2f}")
            
            self._trigger_alert(
                AlertType.COMPENSATION_CLOSED,
                f"Pareja de compensación cerrada: {symbol}",
                {
                    'symbol': symbol,
                    'reason': reason,
                    'total_pnl': total_pnl,
                    'compensation_achieved': compensation.compensation_achieved
                }
            )
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error cerrando pareja de compensación {compensation_id}: {e}")
    
    def _close_compensation_position(self, compensation_id: str, 
                                   exit_price: float, 
                                   reason: str) -> Optional[Dict]:
        """
        Cierra una posición de compensación
        
        Args:
            compensation_id: ID de la compensación
            exit_price: Precio de salida
            reason: Razón del cierre
            
        Returns:
            Registro del trade o None si error
        """
        if compensation_id not in self.compensation_positions:
            return None
        
        compensation = self.compensation_positions[compensation_id]
        
        # Calcular PnL realizado
        if compensation.position_type == 'long':
            realized_pnl = (exit_price - compensation.entry_price) * compensation.quantity
        else:
            realized_pnl = (compensation.entry_price - exit_price) * compensation.quantity
        
        # Crear registro del trade
        trade_record = {
            'symbol': compensation.symbol,
            'entry_price': compensation.entry_price,
            'exit_price': exit_price,
            'quantity': compensation.quantity,
            'position_type': compensation.position_type,
            'entry_time': compensation.entry_time,
            'exit_time': datetime.now(),
            'realized_pnl': realized_pnl,
            'return_pct': (realized_pnl / (compensation.entry_price * compensation.quantity)) * 100,
            'exit_reason': f"Compensation: {reason}",
            'risk_amount': 0,  # Las compensaciones tienen riesgo separado
            'max_drawdown': 0,
            'compensation_id': compensation_id,
            'parent_position_id': compensation.parent_position_id
        }
        
        # Actualizar portfolio
        self.portfolio_value += realized_pnl
        self.trade_history.append(trade_record)
        
        self.logger.info(f"[COMPENSATION] Posición cerrada: {compensation_id} PnL: ${realized_pnl:.2f}")
        
        return trade_record
    
    def get_compensation_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del sistema de compensación
        
        Returns:
            Diccionario con información del sistema de compensación
        """
        active_compensations = []
        
        for comp_id, compensation in self.compensation_positions.items():
            active_compensations.append({
                'id': comp_id,
                'symbol': compensation.symbol,
                'parent_position': compensation.parent_position_id,
                'type': compensation.position_type,
                'entry_price': compensation.entry_price,
                'current_price': compensation.current_price,
                'quantity': compensation.quantity,
                'unrealized_pnl': compensation.unrealized_pnl,
                'target_compensation': compensation.target_compensation_amount,
                'progress_pct': min(100, (compensation.compensation_achieved / 
                                         max(compensation.target_compensation_amount, 1)) * 100)
            })
        
        return {
            'compensation_enabled': self.risk_config.compensation_enabled,
            'active_compensations': len(self.compensation_positions),
            'max_compensation_positions': self.risk_config.max_compensation_positions,
            'compensation_threshold': self.risk_config.compensation_threshold,
            'compensation_details': active_compensations,
            'compensation_pairs': dict(self.compensation_pairs)
        }
        
        # Aquí podría ir código para enviar notificaciones,
        # guardar en base de datos, etc.
    
    def update_portfolio_metrics(self) -> None:
        """Actualiza métricas del portfolio"""
        # Calcular valor total actual
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        current_equity = self.portfolio_value + total_unrealized_pnl
        
        # Actualizar equity curve
        self.equity_curve.append(current_equity)
        
        # Calcular drawdown
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
            self.max_drawdown_reached = max(self.max_drawdown_reached, self.current_drawdown)
        
        # Calcular retorno diario
        if len(self.equity_curve) > 1:
            daily_return = (self.equity_curve[-1] - self.equity_curve[-2]) / self.equity_curve[-2]
            self.daily_returns.append(daily_return)
            
        # Disparar alertas si es necesario
        if self.current_drawdown > self.risk_config.max_drawdown * 0.8:
            self._trigger_alert(
                AlertType.DRAWDOWN_WARNING, 
                f"Drawdown crítico: {self.current_drawdown*100:.1f}% (límite: {self.risk_config.max_drawdown*100}%)",
                {'drawdown': self.current_drawdown, 'max_allowed': self.risk_config.max_drawdown}
            )
            
        # Verificar exposición excesiva del portfolio
        total_exposure = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        if total_exposure > current_equity * self.risk_config.max_portfolio_exposure:
            self._trigger_alert(
                AlertType.MAX_EXPOSURE_EXCEEDED,
                f"Exposición excesiva: {total_exposure:.2f} > {current_equity * self.risk_config.max_portfolio_exposure:.2f}",
                {'exposure': total_exposure, 'max_allowed': current_equity * self.risk_config.max_portfolio_exposure}
            )
    
    def get_risk_metrics(self) -> RiskMetrics:
        """Calcula métricas completas de riesgo"""
        try:
            # Métricas básicas
            total_risk = sum(pos.risk_amount for pos in self.positions.values())
            
            # VaR (Value at Risk)
            if len(self.daily_returns) > 30:
                returns_array = np.array(self.daily_returns)
                var_95 = np.percentile(returns_array, 5) * self.portfolio_value
                expected_shortfall = np.mean(returns_array[returns_array <= np.percentile(returns_array, 5)]) * self.portfolio_value
                portfolio_volatility = np.std(returns_array) * np.sqrt(252)
                
                # Sharpe ratio
                mean_return = np.mean(returns_array) * 252
                sharpe_ratio = mean_return / portfolio_volatility if portfolio_volatility > 0 else 0
                
                # Sortino ratio
                negative_returns = returns_array[returns_array < 0]
                downside_deviation = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0
                sortino_ratio = mean_return / downside_deviation if downside_deviation > 0 else 0
                
            else:
                var_95 = -self.portfolio_value * 0.05  # 5% estimado
                expected_shortfall = -self.portfolio_value * 0.08
                portfolio_volatility = 0.2  # 20% estimado
                sharpe_ratio = 0.0
                sortino_ratio = 0.0
            
            # Concentración por sector (simplificado)
            sector_concentration = self._calculate_sector_concentration()
            
            # Risk-adjusted return
            total_return = (self.portfolio_value - self.risk_config.initial_capital) / self.risk_config.initial_capital
            risk_adjusted_return = total_return / max(portfolio_volatility, 0.01)
            
            return RiskMetrics(
                total_risk=total_risk,
                var_95=var_95,
                expected_shortfall=expected_shortfall,
                max_drawdown=self.max_drawdown_reached,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                correlation_risk=0.0,  # Implementar si es necesario
                sector_concentration=sector_concentration,
                daily_var=var_95 / np.sqrt(252),
                portfolio_volatility=portfolio_volatility,
                risk_adjusted_return=risk_adjusted_return
            )
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error calculando métricas de riesgo: {e}")
            return RiskMetrics(
                total_risk=0, var_95=0, expected_shortfall=0, max_drawdown=0,
                sharpe_ratio=0, sortino_ratio=0, correlation_risk=0,
                sector_concentration={}, daily_var=0, portfolio_volatility=0,
                risk_adjusted_return=0
            )
    
    def _calculate_sector_concentration(self) -> Dict[str, float]:
        """Calcula concentración por sector/tipo de activo"""
        sector_exposure = {}
        total_exposure = 0
        
        for position in self.positions.values():
            symbol_config = self._get_symbol_config_safe(position.symbol)
            sector = symbol_config.get("asset_type", "unknown")
            exposure = position.quantity * position.current_price
            sector_exposure[sector] = sector_exposure.get(sector, 0) + exposure
            total_exposure += exposure
        
        # Convertir a porcentajes
        if total_exposure > 0:
            for sector in sector_exposure:
                sector_exposure[sector] = (sector_exposure[sector] / total_exposure) * 100
        
        return sector_exposure
    
    def can_open_new_position(self, symbol: str, position_value: float) -> Tuple[bool, str]:
        """Verifica si se puede abrir una nueva posición"""
        # Verificar límite de posiciones
        if len(self.positions) >= self.max_positions:
            return False, "Límite máximo de posiciones alcanzado"
        
        # Verificar drawdown
        if self.current_drawdown > self.risk_config.max_drawdown:
            return False, f"Drawdown excede límite: {self.current_drawdown*100:.1f}%"
        
        # Verificar exposición por sector
        symbol_config = self._get_symbol_config_safe(symbol)
        if symbol_config:
            sector_concentration = self._calculate_sector_concentration()
            current_sector_exposure = sector_concentration.get(symbol_config.get("asset_type", "unknown"), 0)
            new_exposure_pct = (position_value / self.portfolio_value) * 100
            
            if current_sector_exposure + new_exposure_pct > self.max_sector_exposure * 100:
                return False, f"Límite de exposición por sector excedido"
        
        # Verificar capital disponible
        used_capital = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        available_capital = self.portfolio_value - used_capital
        
        if position_value > available_capital * 0.9:  # Usar máximo 90% del capital disponible
            return False, "Capital insuficiente"
        
        return True, "OK"
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de todas las posiciones"""
        if not self.positions:
            return {
                'total_positions': 0,
                'total_exposure': 0,
                'total_unrealized_pnl': 0,
                'positions': []
            }
        
        positions_data = []
        total_exposure = 0
        total_unrealized_pnl = 0
        
        for symbol, position in self.positions.items():
            exposure = position.quantity * position.current_price
            total_exposure += exposure
            total_unrealized_pnl += position.unrealized_pnl
            
            positions_data.append({
                'symbol': symbol,
                'type': position.position_type,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'exposure': exposure,
                'unrealized_pnl': position.unrealized_pnl,
                'return_pct': (position.unrealized_pnl / exposure) * 100 if exposure > 0 else 0,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'entry_time': position.entry_time.isoformat()
            })
        
        return {
            'total_positions': len(self.positions),
            'total_exposure': total_exposure,
            'total_unrealized_pnl': total_unrealized_pnl,
            'exposure_pct': (total_exposure / self.portfolio_value) * 100,
            'positions': positions_data
        }

    # === MÉTODOS AVANZADOS INTEGRADOS DE ADVANCED_RISK_MANAGER ===

    def calculate_drawdown_adjustment(self) -> float:
        """Ajusta el tamaño de posición basado en drawdown actual (de advanced_risk_manager)"""
        if self.current_drawdown <= 0.02:  # Menos de 2%
            return 1.0
        elif self.current_drawdown <= 0.05:  # 2-5%
            return 0.8
        elif self.current_drawdown <= 0.08:  # 5-8%
            return 0.6
        elif self.current_drawdown <= 0.12:  # 8-12%
            return 0.4
        else:  # Más de 12%
            return 0.2

    def calculate_correlation_adjustment(self, symbol: str) -> float:
        """Ajusta por correlación con posiciones existentes (de advanced_risk_manager)"""
        if not self.positions:
            return 1.0

        # Simplificación: asumir correlaciones por tipo de asset
        crypto_symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'BNB']

        symbol_type = None
        for crypto in crypto_symbols:
            if crypto in symbol.upper():
                symbol_type = 'crypto'
                break

        if symbol_type == 'crypto':
            crypto_positions = sum(1 for pos_symbol in self.positions.keys()
                                 if any(crypto in pos_symbol.upper() for crypto in crypto_symbols))

            if crypto_positions >= 3:
                return 0.6  # Reducir tamaño si ya hay muchas posiciones crypto
            elif crypto_positions >= 2:
                return 0.8
            else:
                return 1.0

        return 1.0

    def calculate_performance_adjustment(self) -> float:
        """Ajusta basado en performance reciente (de advanced_risk_manager)"""
        if len(self.daily_returns) < 10:
            return 1.0

        recent_returns = self.daily_returns[-10:]
        avg_return = np.mean(recent_returns)

        if avg_return > 0.002:  # Más de 0.2% diario promedio
            return min(1.3, 1 + avg_return * 50)  # Incrementar gradualmente
        elif avg_return < -0.002:  # Pérdidas
            return max(0.5, 1 + avg_return * 50)  # Reducir gradualmente
        else:
            return 1.0

    def should_reduce_exposure(self) -> bool:
        """Determina si se debe reducir la exposición (de advanced_risk_manager)"""
        # Calcular métricas actuales
        total_exposure = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        portfolio_heat = total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0

        # Calcular VaR diario simplificado
        daily_var = 0.0
        if len(self.daily_returns) >= 20:
            returns_array = np.array(self.daily_returns[-20:])
            daily_var = abs(np.percentile(returns_array, 5))

        # Calcular score de riesgo compuesto
        risk_components = [
            min(self.current_drawdown / self.risk_config.max_drawdown, 1.0) * 30,  # 30% peso
            min(portfolio_heat / 1.0, 1.0) * 25,  # 25% peso
            min(daily_var / 0.05, 1.0) * 20,  # 20% peso
            min(len(self.positions) / self.max_positions, 1.0) * 25  # 25% peso
        ]

        risk_score = sum(risk_components)

        # Condiciones para reducir exposición
        conditions = [
            self.current_drawdown > self.risk_config.max_drawdown * 0.8,  # 80% del máximo DD
            portfolio_heat > 0.8,  # Más de 80% de exposición
            risk_score > 75,  # Score de riesgo alto
            len(self.positions) >= self.max_positions
        ]

        return any(conditions)

    def should_halt_trading(self) -> bool:
        """Determina si se debe detener el trading completamente (de advanced_risk_manager)"""
        # Calcular métricas actuales
        total_exposure = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        portfolio_heat = total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0
        
        # Para backtesting, ser mucho más permisivo
        if hasattr(self, 'portfolio_value') and self.portfolio_value > 100:  # Si estamos en backtesting
            # Solo detener si hay pérdida catastrófica (>95%)
            if self.portfolio_value < self.risk_config.initial_capital * 0.05:
                self._trigger_alert(
                    AlertType.CIRCUIT_BREAKER,
                    "CIRCUIT BREAKER ACTIVADO: Pérdida catastrófica en backtesting",
                    {
                        'portfolio_value': self.portfolio_value,
                        'initial_capital': self.risk_config.initial_capital
                    }
                )
                return True
            return False
        
        # Condiciones normales para trading real (más relajadas para backtesting)
        critical_conditions = [
            self.current_drawdown > self.risk_config.max_drawdown * 4,  # Drawdown muy alto (60% para backtesting)
            portfolio_heat > 5.0,  # Sobre-exposición muy crítica (500% para backtesting)
            len(self.positions) > self.max_positions * 5,  # Muchas posiciones (50 para backtesting)
            self.portfolio_value < self.risk_config.initial_capital * 0.2  # Pérdida del 80% (más permisivo)
        ]

        if any(critical_conditions):
            self._trigger_alert(
                AlertType.CIRCUIT_BREAKER,
                "CIRCUIT BREAKER ACTIVADO: Trading detenido por condiciones criticas",
                {
                    'drawdown': self.current_drawdown,
                    'exposure': portfolio_heat,
                    'positions': len(self.positions),
                    'portfolio_value': self.portfolio_value
                }
            )
            return True

        return False

    def optimize_risk_level(self, recent_performance: List[float]) -> str:
        """Optimización adaptativa del nivel de riesgo (de advanced_risk_manager)"""
        if len(recent_performance) < 20:
            return "moderate"

        # Analizar performance reciente
        avg_return = np.mean(recent_performance)
        volatility = np.std(recent_performance)
        sharpe_ratio = avg_return / volatility if volatility > 0 else 0

        # Calcular métricas de consistencia
        positive_days = sum(1 for r in recent_performance if r > 0)
        consistency = positive_days / len(recent_performance)

        # Lógica de optimización
        if sharpe_ratio > 1.5 and consistency > 0.6:
            return "aggressive"
        elif sharpe_ratio > 1.0 and consistency > 0.5:
            return "moderate"
        elif sharpe_ratio < 0.5 or consistency < 0.4:
            return "conservative"
        else:
            return "moderate"

    def get_enhanced_risk_report(self) -> Dict:
        """Genera reporte de riesgo mejorado con métricas avanzadas"""
        base_metrics = self.get_risk_metrics()

        # Agregar métricas avanzadas
        enhanced_report = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_value': self.portfolio_value,
            'current_drawdown': self.current_drawdown * 100,
            'max_drawdown': self.max_drawdown_reached * 100,
            'total_positions': len(self.positions),
            'total_exposure': sum(pos.quantity * pos.current_price for pos in self.positions.values()),

            # Métricas base
            'sharpe_ratio': base_metrics.sharpe_ratio,
            'sortino_ratio': base_metrics.sortino_ratio,
            'var_95': base_metrics.var_95,
            'expected_shortfall': base_metrics.expected_shortfall,

            # Ajustes dinámicos
            'drawdown_adjustment': self.calculate_drawdown_adjustment(),
            'performance_adjustment': self.calculate_performance_adjustment(),
            'should_reduce_exposure': self.should_reduce_exposure(),
            'should_halt_trading': self.should_halt_trading(),

            # Métricas de posiciones
            'positions_summary': self.get_position_summary(),

            # Alertas activas
            'active_alerts': []
        }

        return enhanced_report


class KellyCriterion:
    """
    Implementación del criterio de Kelly para sizing de posiciones.
    
    El criterio de Kelly es una fórmula matemática que determina la
    fracción óptima del capital a asignar a una inversión para maximizar
    el crecimiento logarítmico del capital a largo plazo.
    """
    
    def __init__(self, lookback_period: int = 50):
        """
        Inicializa el calculador de Kelly
        
        Args:
            lookback_period: Número de trades a considerar para el cálculo
        """
        self.lookback_period = lookback_period
        self.trade_history: List[Dict] = []
        self.logger = logging.getLogger(__name__ + ".KellyCriterion")
    
    def calculate_kelly_fraction(self, 
                               win_rate: float, 
                               avg_win: float, 
                               avg_loss: float,
                               confidence_factor: float = 0.5) -> float:
        """
        Calcula la fracción óptima de Kelly
        
        Args:
            win_rate: Tasa de ganancia (0-1)
            avg_win: Ganancia promedio
            avg_loss: Pérdida promedio (valor positivo)
            confidence_factor: Factor de confianza para reducir el Kelly (0-1)
            
        Returns:
            Fracción de Kelly ajustada
        """
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0
        
        # Fórmula de Kelly: f = (bp - q) / b
        # b = avg_win / avg_loss (odds)
        # p = win_rate
        # q = 1 - win_rate
        
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Aplicar factor de confianza para ser más conservadores
        kelly_adjusted = kelly_fraction * confidence_factor
        
        # Limitar el Kelly máximo al 25% del capital
        kelly_final = min(max(kelly_adjusted, 0.01), 0.25)
        
        self.logger.info(f"Kelly calculado: {kelly_fraction:.3f}, Ajustado: {kelly_final:.3f}")
        
        return kelly_final
    
    def update_trade_history(self, pnl: float, success: bool):
        """
        Actualiza el historial de trades para el cálculo de Kelly
        
        Args:
            pnl: Ganancia/pérdida del trade como fracción del capital
            success: True si el trade fue exitoso
        """
        self.trade_history.append({
            'pnl': pnl,
            'success': success,
            'timestamp': datetime.now()
        })
        
        # Mantener solo el período de lookback
        if len(self.trade_history) > self.lookback_period:
            self.trade_history = self.trade_history[-self.lookback_period:]
    
    def get_current_metrics(self) -> Dict[str, float]:
        """
        Obtiene las métricas actuales para el cálculo de Kelly
        
        Returns:
            Diccionario con win_rate, avg_win, avg_loss, y kelly_fraction
        """
        if len(self.trade_history) < 10:  # Mínimo 10 trades
            return {
                'win_rate': 0.5,
                'avg_win': 0.02,
                'avg_loss': 0.01,
                'kelly_fraction': 0.05  # Valor conservador por defecto
            }
        
        wins = [t['pnl'] for t in self.trade_history if t['success']]
        losses = [abs(t['pnl']) for t in self.trade_history if not t['success']]
        
        win_rate = len(wins) / len(self.trade_history)
        avg_win = np.mean(wins) if wins else 0.02
        avg_loss = np.mean(losses) if losses else 0.01
        
        kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
        
        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'kelly_fraction': kelly_fraction
        }

class KellyCriterion:
    """Implementación del criterio de Kelly para sizing de posiciones"""
    
    def __init__(self, lookback_period: int = 50):
        self.lookback_period = lookback_period
        self.trade_history: List[Dict] = []
        self.logger = logging.getLogger(__name__)
        
    def calculate_kelly_fraction(self, 
                                win_rate: float, 
                                avg_win: float, 
                                avg_loss: float,
                                confidence_factor: float = 0.25) -> float:
        """
        Calcula la fracción óptima de Kelly
        
        Args:
            win_rate: Tasa de ganancia (0-1)
            avg_win: Ganancia promedio
            avg_loss: Pérdida promedio (valor positivo)
            confidence_factor: Factor de confianza para reducir el Kelly (0-1)
            
        Returns:
            Fracción de Kelly ajustada
        """
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0
            
        # Fórmula de Kelly: f = (bp - q) / b
        # b = avg_win / avg_loss (odds)
        # p = win_rate
        # q = 1 - win_rate
        
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Aplicar factor de confianza para ser más conservadores
        kelly_adjusted = kelly_fraction * confidence_factor
        
        # Limitar el Kelly máximo al 25% del capital
        kelly_final = min(max(kelly_adjusted, 0.01), 0.25)
        
        self.logger.info(f"Kelly calculado: {kelly_fraction:.3f}, Ajustado: {kelly_final:.3f}")
        
        return kelly_final
    
    def update_trade_history(self, pnl: float, success: bool):
        """Actualiza el historial de trades para el cálculo de Kelly"""
        self.trade_history.append({
            'pnl': pnl,
            'success': success,
            'timestamp': datetime.now()
        })
        
        # Mantener solo el período de lookback
        if len(self.trade_history) > self.lookback_period:
            self.trade_history = self.trade_history[-self.lookback_period:]
    
    def get_current_metrics(self) -> Dict[str, float]:
        """Obtiene las métricas actuales para el cálculo de Kelly"""
        if len(self.trade_history) < 10:  # Mínimo 10 trades
            return {
                'win_rate': 0.5,
                'avg_win': 0.02,
                'avg_loss': 0.01,
                'kelly_fraction': 0.01
            }
        
        wins = [t['pnl'] for t in self.trade_history if t['success']]
        losses = [abs(t['pnl']) for t in self.trade_history if not t['success']]
        
        win_rate = len(wins) / len(self.trade_history)
        avg_win = np.mean(wins) if wins else 0.02
        avg_loss = np.mean(losses) if losses else 0.01
        
        kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)
        
        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'kelly_fraction': kelly_fraction
        }

# Instancia global del gestor de riesgo
risk_manager = AdvancedRiskManager()

def get_risk_manager() -> AdvancedRiskManager:
    """Obtiene la instancia global del gestor de riesgo"""
    return risk_manager
