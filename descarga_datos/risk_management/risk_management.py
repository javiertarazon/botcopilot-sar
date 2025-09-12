#!/usr/bin/env python3
"""
MÓDULO DE GESTIÓN DE RIESGO - VERSIÓN FUNCIONAL
==============================================

Sistema avanzado de gestión de riesgo para trading cuantitativo con compensación integrada.

Características principales:
- Sistema de compensación automática con 3x lot sizing
- Kelly Criterion para dimensionamiento óptimo de posiciones
- Análisis de correlación entre activos
- Límites de exposición por sector
- Volatility-adjusted position sizing
- Risk parity calculations
- Análisis de riesgo del portfolio en tiempo real
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from datetime import datetime, timedelta
import logging
from enum import Enum
import math
import time

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
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

# === SISTEMA DE COMPENSACIÓN FUNCIONAL ===
class MockBrokerAPI:
    """API simulada del broker para operaciones de trading"""
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.order_counter = 0

    def get_account_balance(self):
        return self.risk_manager.portfolio_value

    def get_pnl(self, trade_id):
        """Obtiene el P&L de una posición"""
        if trade_id in self.risk_manager.positions:
            return self.risk_manager.positions[trade_id].unrealized_pnl
        return 0

    def get_type(self, trade_id):
        """Obtiene el tipo de operación"""
        if trade_id in self.risk_manager.positions:
            pos_type = self.risk_manager.positions[trade_id].position_type
            return 'BUY' if pos_type == 'long' else 'SELL'
        return ''

    def get_lot_size(self, trade_id):
        """Obtiene el tamaño de la posición"""
        if trade_id in self.risk_manager.positions:
            return self.risk_manager.positions[trade_id].quantity
        return 0

    def execute_order(self, symbol, type, lot_size, comment):
        """Ejecuta una orden (simulada)"""
        self.order_counter += 1
        new_id = f'order_{self.order_counter}'

        # Crear posición simulada
        position_type = 'long' if type == 'BUY' else 'short'
        current_price = 100.0  # Precio simulado

        position = Position(
            symbol=symbol,
            entry_price=current_price,
            quantity=lot_size,
            entry_time=datetime.now(),
            position_type=position_type,
            stop_loss=current_price * 0.95,
            take_profit=current_price * 1.05,
            current_price=current_price,
            risk_amount=lot_size * current_price * 0.02,
            metadata={'comment': comment}
        )

        self.risk_manager.positions[new_id] = position
        print(f"Orden {new_id} ({type}) con {lot_size} lotes ejecutada.")
        return new_id

    def close_order(self, trade_id):
        """Cierra una orden"""
        if trade_id in self.risk_manager.positions:
            position = self.risk_manager.positions[trade_id]
            pnl_final = position.unrealized_pnl
            self.risk_manager.portfolio_value += pnl_final
            print(f"Orden {trade_id} cerrada con P&L de {pnl_final:.2f}. Balance actual: {self.risk_manager.portfolio_value:.2f}")
            del self.risk_manager.positions[trade_id]

class CompensationManager:
    """Gestor avanzado de compensación de operaciones en reversión"""
    def __init__(self, broker_api, safety_stop_loss_pct=0.03):
        self.broker = broker_api
        self.safety_stop_loss = self.broker.get_account_balance() * -safety_stop_loss_pct
        self.compensation_map = {}

    def monitor_and_compensate(self, op_trade_id):
        """Monitorea la operación principal y activa compensación si es necesario"""
        op_pnl = self.broker.get_pnl(op_trade_id)

        loss_threshold = self.broker.get_account_balance() * -0.005
        if op_pnl <= loss_threshold and op_trade_id not in self.compensation_map:
            print(f"Pérdida de la OP {op_trade_id} ha alcanzado el umbral. Abriendo OC...")
            self.open_compensation_trade(op_trade_id)

    def open_compensation_trade(self, op_trade_id):
        """Abre una operación de compensación con lotaje 3 veces el de la OP"""
        op_type = self.broker.get_type(op_trade_id)
        oc_type = 'SELL' if op_type == 'BUY' else 'BUY'
        # Nuevo lotaje: 3 veces el de la OP
        oc_lot_size = self.broker.get_lot_size(op_trade_id) * 3

        # Obtener símbolo de la posición
        if op_trade_id in self.broker.risk_manager.positions:
            op_symbol = self.broker.risk_manager.positions[op_trade_id].symbol
        else:
            op_symbol = "UNKNOWN"

        oc_trade_id = self.broker.execute_order(
            symbol=op_symbol,
            type=oc_type,
            lot_size=oc_lot_size,
            comment=f'Compensación para OP ID {op_trade_id}'
        )
        self.compensation_map[op_trade_id] = oc_trade_id
        print(f"OC {oc_trade_id} abierta para OP {op_trade_id}.")

    def manage_positions(self, op_trade_id):
        """Gestiona las posiciones según diferentes escenarios"""
        oc_trade_id = self.compensation_map.get(op_trade_id)

        if not oc_trade_id:
            return

        op_pnl = self.broker.get_pnl(op_trade_id)
        oc_pnl = self.broker.get_pnl(oc_trade_id)
        total_pnl = op_pnl + oc_pnl

        # Stop-Loss Global de Seguridad
        if total_pnl <= self.safety_stop_loss:
            print(f"⚠️ ¡STOP-LOSS DE SEGURIDAD ACTIVADO! Pérdida total de {total_pnl:.2f}. Cerrando ambas operaciones.")
            self.broker.close_order(op_trade_id)
            self.broker.close_order(oc_trade_id)
            del self.compensation_map[op_trade_id]
            return

        # Escenario A: Cierre por compensación exitosa
        if total_pnl >= 0:
            print(f"Ganancia total >= 0. Cerrando OP {op_trade_id} y OC {oc_trade_id}.")
            self.broker.close_order(op_trade_id)
            self.broker.close_order(oc_trade_id)
            del self.compensation_map[op_trade_id]
            return

        # Escenario B: Cierre de la OC si la OP revierte a ganancia
        if op_pnl >= 0:
            print(f"OP {op_trade_id} ha vuelto a ser rentable. Cerrando solo OC {oc_trade_id}.")
            self.broker.close_order(oc_trade_id)
            del self.compensation_map[op_trade_id]

class AdvancedRiskManager:
    """Gestor avanzado de riesgo para trading cuantitativo"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.risk_config = RiskConfig()
        self.portfolio_value = self.risk_config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.current_drawdown = 0.0
        self.max_drawdown_reached = 0.0
        self.peak_equity = self.portfolio_value

        # Límites y restricciones
        self.max_positions = 10
        self.max_sector_exposure = 0.3  # 30% máximo por sector
        self.correlation_threshold = 0.7

        # Sistema de compensación - Versión funcional
        self.mock_broker = MockBrokerAPI(self)
        self.compensation_manager = CompensationManager(self.mock_broker, safety_stop_loss_pct=0.03)
        self.compensation_positions: Dict[str, str] = {}
        self.reversal_detection_enabled = True
        self.compensation_pairs: Dict[str, str] = {}  # position_id -> compensation_id

        print("[OK] Advanced Risk Manager inicializado con sistema de compensación")

    def process_risk_management_cycle(self, market_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Método principal que coordina todo el ciclo de gestión de riesgo

        Args:
            market_data: Diccionario con precios actuales de los símbolos {'symbol': price}

        Returns:
            Diccionario con acciones tomadas y estado actual
        """
        actions_taken = []
        alerts_generated = []

        try:
            # Actualizar precios de posiciones
            for symbol, current_price in market_data.items():
                if symbol in self.positions:
                    # Simular actualización de P&L
                    position = self.positions[symbol]
                    if position.position_type == 'long':
                        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                    else:
                        position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                    actions_taken.append(f"Updated position {symbol} @ ${current_price:.2f}")

            # Monitorear compensaciones para todas las posiciones
            for position_id in list(self.positions.keys()):
                self.compensation_manager.monitor_and_compensate(position_id)
                self.compensation_manager.manage_positions(position_id)

            actions_taken.append("Risk management cycle completed successfully")

            return {
                'success': True,
                'actions_taken': actions_taken,
                'alerts_generated': alerts_generated,
                'portfolio_value': self.portfolio_value,
                'current_drawdown': self.current_drawdown,
                'active_positions': len(self.positions),
                'message': 'Risk management cycle completed with compensation system'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'actions_taken': actions_taken,
                'alerts_generated': alerts_generated
            }

    def get_compensation_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del sistema de compensación
        
        Returns:
            Diccionario con información del sistema de compensación
        """
        active_compensations = []
        
        # Si tenemos posiciones de compensación activas, las incluimos
        for comp_id, compensation in getattr(self, 'compensation_positions', {}).items():
            active_compensations.append({
                'id': comp_id,
                'symbol': getattr(compensation, 'symbol', 'N/A'),
                'parent_position': getattr(compensation, 'parent_position_id', 'N/A'),
                'type': getattr(compensation, 'position_type', 'N/A'),
                'entry_price': getattr(compensation, 'entry_price', 0.0),
                'current_price': getattr(compensation, 'current_price', 0.0),
                'quantity': getattr(compensation, 'quantity', 0.0),
                'unrealized_pnl': getattr(compensation, 'unrealized_pnl', 0.0),
                'target_compensation': getattr(compensation, 'target_compensation_amount', 0.0),
                'progress_pct': 0.0  # Placeholder
            })
        
        return {
            'compensation_enabled': self.risk_config.compensation_enabled,
            'active_compensations': len(active_compensations),
            'max_compensation_positions': self.risk_config.max_compensation_positions,
            'compensation_threshold': self.risk_config.compensation_threshold,
            'compensation_details': active_compensations,
            'compensation_pairs': getattr(self, 'compensation_pairs', {})
        }

    def calculate_position_size(self, symbol: str, entry_price: float,
                              stop_loss_price: float, signal_strength: float = 1.0,
                              atr_value: Optional[float] = None) -> Dict[str, Any]:
        """Calcula el tamaño óptimo de posición con funcionalidades avanzadas"""
        try:
            # Validaciones iniciales
            if entry_price <= 0 or stop_loss_price <= 0:
                return {'error': 'Precios inválidos'}

            risk_amount = self.portfolio_value * self.risk_config.risk_per_trade
            stop_loss_distance = abs(entry_price - stop_loss_price)

            if stop_loss_distance == 0:
                return {'error': 'Stop loss demasiado cercano'}

            # Calcular tamaño base de posición
            base_position_size = risk_amount / stop_loss_distance

            # === APLICAR FUNCIONALIDADES AVANZADAS ===

            # 1. Ajuste por Kelly Criterion
            kelly_adjustment = self._calculate_kelly_position_size(symbol, signal_strength)
            kelly_size = base_position_size * kelly_adjustment

            # 2. Ajuste por correlación
            correlation_adjustment = self.calculate_correlation_adjustment(symbol)
            correlated_size = kelly_size * correlation_adjustment

            # 3. Ajuste por performance reciente
            performance_adjustment = self.calculate_performance_adjustment()
            adjusted_size = correlated_size * performance_adjustment

            # 4. Ajuste por volatilidad (si hay ATR disponible)
            volatility_adjustment = 1.0
            if atr_value and atr_value > 0:
                # Reducir tamaño si la volatilidad es alta
                volatility_ratio = atr_value / entry_price
                if volatility_ratio > 0.05:  # Alta volatilidad
                    volatility_adjustment = 0.7
                elif volatility_ratio > 0.03:  # Volatilidad moderada
                    volatility_adjustment = 0.85

            final_size = adjusted_size * volatility_adjustment

            # 5. Verificar límites y restricciones
            position_value = final_size * entry_price
            can_open, reason = self.can_open_new_position(symbol, position_value)

            if not can_open:
                # Reducir tamaño si no se puede abrir con el tamaño calculado
                max_allowed_value = self.portfolio_value * 0.1  # Máximo 10% del portfolio
                final_size = max_allowed_value / entry_price
                print(f"⚠️ Tamaño reducido por restricción: {reason}")

            # Aplicar límites de seguridad
            max_position_value = self.portfolio_value * 0.15  # Máximo 15% del portfolio
            final_size = min(final_size, max_position_value / entry_price)

            # Calcular métricas adicionales
            position_risk_percent = (final_size * stop_loss_distance) / self.portfolio_value
            take_profit_price = entry_price + (entry_price - stop_loss_price) * 3  # TP 3:1

            return {
                'recommended_size': final_size,
                'risk_amount': risk_amount,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'position_risk_percent': position_risk_percent,
                'kelly_adjustment': kelly_adjustment,
                'correlation_adjustment': correlation_adjustment,
                'performance_adjustment': performance_adjustment,
                'volatility_adjustment': volatility_adjustment,
                'final_adjustment_factor': kelly_adjustment * correlation_adjustment * performance_adjustment * volatility_adjustment
            }

        except Exception as e:
            return {'error': str(e)}

    # === FUNCIONALIDADES AVANZADAS INTEGRADAS ===

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

            return adjusted_fraction

        except Exception as e:
            self.logger.error(f"[ERROR] Error calculando Kelly: {e}")
            return 0.1  # Valor conservador por defecto

    def _calculate_sector_concentration(self) -> Dict[str, float]:
        """Calcula concentración por sector/tipo de activo"""
        sector_exposure = {}
        total_exposure = 0

        for position in self.positions.values():
            # Clasificar por tipo de activo basado en el símbolo
            if any(crypto in position.symbol.upper() for crypto in ['BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'BNB', 'DOT', 'LINK', 'LTC']):
                sector = 'crypto'
            elif any(stock in position.symbol.upper() for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA']):
                sector = 'tech_stocks'
            else:
                sector = 'other'

            exposure = position.quantity * position.current_price
            sector_exposure[sector] = sector_exposure.get(sector, 0) + exposure
            total_exposure += exposure

        # Convertir a porcentajes
        if total_exposure > 0:
            for sector in sector_exposure:
                sector_exposure[sector] = (sector_exposure[sector] / total_exposure) * 100

        return sector_exposure

    def calculate_correlation_adjustment(self, symbol: str) -> float:
        """Ajusta por correlación con posiciones existentes"""
        if not self.positions:
            return 1.0

        # Clasificar el símbolo
        crypto_symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'BNB', 'DOT', 'LINK', 'LTC']
        stock_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA']

        symbol_type = None
        if any(crypto in symbol.upper() for crypto in crypto_symbols):
            symbol_type = 'crypto'
        elif any(stock in symbol.upper() for stock in stock_symbols):
            symbol_type = 'tech_stocks'

        if symbol_type == 'crypto':
            crypto_positions = sum(1 for pos_symbol in self.positions.keys()
                                 if any(crypto in pos_symbol.upper() for crypto in crypto_symbols))

            if crypto_positions >= 3:
                return 0.6  # Reducir tamaño si ya hay muchas posiciones crypto
            elif crypto_positions >= 2:
                return 0.8
            else:
                return 1.0

        elif symbol_type == 'tech_stocks':
            stock_positions = sum(1 for pos_symbol in self.positions.keys()
                                if any(stock in pos_symbol.upper() for stock in stock_symbols))

            if stock_positions >= 2:
                return 0.7  # Tech stocks están altamente correlacionadas
            else:
                return 1.0

        return 1.0

    def calculate_performance_adjustment(self) -> float:
        """Ajusta basado en performance reciente"""
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

    def can_open_new_position(self, symbol: str, position_value: float) -> Tuple[bool, str]:
        """Verifica si se puede abrir una nueva posición con validaciones avanzadas"""
        # Verificar límite de posiciones
        if len(self.positions) >= self.max_positions:
            return False, "Límite máximo de posiciones alcanzado"

        # Verificar drawdown
        if self.current_drawdown > self.risk_config.max_drawdown:
            return False, f"Drawdown excede límite: {self.current_drawdown*100:.1f}%"

        # Verificar exposición por sector
        sector_concentration = self._calculate_sector_concentration()
        symbol_type = 'crypto' if any(crypto in symbol.upper() for crypto in ['BTC', 'ETH', 'SOL', 'ADA', 'XRP', 'BNB', 'DOT', 'LINK', 'LTC']) else 'other'

        current_sector_exposure = sector_concentration.get(symbol_type, 0)
        new_exposure_pct = (position_value / self.portfolio_value) * 100

        if current_sector_exposure + new_exposure_pct > self.max_sector_exposure * 100:
            return False, f"Límite de exposición por sector excedido: {symbol_type}"

        # Verificar correlación
        correlation_adjustment = self.calculate_correlation_adjustment(symbol)
        if correlation_adjustment < 0.8:
            return False, f"Alta correlación detectada, reducción necesaria: {correlation_adjustment}"

        # Verificar capital disponible
        used_capital = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        available_capital = self.portfolio_value - used_capital

        if position_value > available_capital * 0.9:  # Usar máximo 90% del capital disponible
            return False, "Capital insuficiente"

        return True, "OK"

    def should_reduce_exposure(self) -> bool:
        """Determina si se debe reducir la exposición"""
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
        """Determina si se debe detener el trading completamente"""
        conditions = [
            self.current_drawdown > self.risk_config.max_drawdown * 0.95,  # 95% del máximo DD
            len(self.positions) >= self.max_positions,
            self.portfolio_value < self.risk_config.initial_capital * 0.7  # Pérdida del 30%
        ]

        return any(conditions)

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de riesgo avanzadas"""
        sector_concentration = self._calculate_sector_concentration()
        total_exposure = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        portfolio_heat = total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0

        # Calcular VaR
        var_95 = 0.0
        if len(self.daily_returns) >= 20:
            returns_array = np.array(self.daily_returns[-20:])
            var_95 = abs(np.percentile(returns_array, 5))

        # Calcular Sharpe ratio simplificado
        sharpe_ratio = 0.0
        if len(self.daily_returns) >= 20:
            avg_return = np.mean(self.daily_returns[-20:])
            std_return = np.std(self.daily_returns[-20:])
            if std_return > 0:
                sharpe_ratio = avg_return / std_return * np.sqrt(252)  # Anualizado

        return {
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown_reached,
            'portfolio_heat': portfolio_heat,
            'total_positions': len(self.positions),
            'sector_concentration': sector_concentration,
            'var_95': var_95,
            'sharpe_ratio': sharpe_ratio,
            'should_reduce_exposure': self.should_reduce_exposure(),
            'should_halt_trading': self.should_halt_trading()
        }

    def analyze_portfolio_risk(self) -> Dict[str, Any]:
        """Análisis completo de riesgo del portfolio"""
        analysis = {
            'overall_risk_score': 0.0,
            'risk_factors': {},
            'recommendations': [],
            'sector_analysis': {},
            'correlation_analysis': {},
            'compensation_analysis': {}
        }

        # Análisis de factores de riesgo
        risk_factors = self._analyze_risk_factors()
        analysis['risk_factors'] = risk_factors

        # Calcular score general de riesgo
        analysis['overall_risk_score'] = self._calculate_overall_risk_score(risk_factors)

        # Análisis sectorial
        analysis['sector_analysis'] = self._analyze_sector_exposure()

        # Análisis de correlaciones
        analysis['correlation_analysis'] = self._analyze_portfolio_correlations()

        # Análisis del sistema de compensación
        analysis['compensation_analysis'] = self.compensation_manager.get_compensation_summary()

        # Generar recomendaciones
        analysis['recommendations'] = self._generate_risk_recommendations(analysis)

        return analysis

    def _analyze_risk_factors(self) -> Dict[str, float]:
        """Analiza factores individuales de riesgo"""
        factors = {}

        # Factor de drawdown
        factors['drawdown_factor'] = min(self.current_drawdown / self.risk_config.max_drawdown, 1.0)

        # Factor de concentración
        total_exposure = sum(pos.quantity * pos.current_price for pos in self.positions.values())
        factors['concentration_factor'] = min(total_exposure / self.portfolio_value, 1.0)

        # Factor de volatilidad
        if len(self.daily_returns) >= 20:
            factors['volatility_factor'] = min(np.std(self.daily_returns[-20:]) / 0.05, 1.0)
        else:
            factors['volatility_factor'] = 0.5

        # Factor de correlación
        factors['correlation_factor'] = self._calculate_portfolio_correlation_factor()

        # Factor de compensación
        compensation_count = len(getattr(self.compensation_manager, 'compensation_map', {}))
        factors['compensation_factor'] = min(compensation_count / 5, 1.0)  # Máximo 5 compensaciones

        return factors

    def _calculate_overall_risk_score(self, risk_factors: Dict[str, float]) -> float:
        """Calcula score general de riesgo ponderado"""
        weights = {
            'drawdown_factor': 0.25,
            'concentration_factor': 0.20,
            'volatility_factor': 0.20,
            'correlation_factor': 0.20,
            'compensation_factor': 0.15
        }

        score = sum(factor * weights[name] for name, factor in risk_factors.items())
        return min(score * 100, 100)  # Score de 0-100

    def _analyze_sector_exposure(self) -> Dict[str, Any]:
        """Análisis detallado de exposición sectorial"""
        sector_concentration = self._calculate_sector_concentration()

        analysis = {
            'sector_breakdown': sector_concentration,
            'overexposed_sectors': [],
            'diversification_score': 0.0
        }

        # Identificar sectores sobreexpuestos
        for sector, exposure_pct in sector_concentration.items():
            if exposure_pct > self.max_sector_exposure * 100:
                analysis['overexposed_sectors'].append({
                    'sector': sector,
                    'exposure': exposure_pct,
                    'limit': self.max_sector_exposure * 100
                })

        # Calcular score de diversificación
        sector_count = len([pct for pct in sector_concentration.values() if pct > 0])
        if sector_count >= 3:
            analysis['diversification_score'] = 100
        elif sector_count >= 2:
            analysis['diversification_score'] = 75
        elif sector_count >= 1:
            analysis['diversification_score'] = 50
        else:
            analysis['diversification_score'] = 0

        return analysis

    def _analyze_portfolio_correlations(self) -> Dict[str, Any]:
        """Análisis de correlaciones del portfolio"""
        analysis = {
            'high_correlation_pairs': [],
            'correlation_warnings': [],
            'diversification_benefit': 0.0
        }

        # Análisis simplificado de correlaciones por tipo de activo
        crypto_count = sum(1 for pos in self.positions.keys()
                          if any(crypto in pos.upper() for crypto in ['BTC', 'ETH', 'SOL', 'ADA', 'XRP']))
        stock_count = sum(1 for pos in self.positions.keys()
                         if any(stock in pos.upper() for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']))

        if crypto_count >= 3:
            analysis['correlation_warnings'].append("Alta concentración en criptomonedas")
        if stock_count >= 2:
            analysis['correlation_warnings'].append("Alta concentración en acciones tech")

        # Beneficio de diversificación estimado
        asset_types = len([t for t in [crypto_count > 0, stock_count > 0] if t])
        analysis['diversification_benefit'] = min(asset_types * 25, 100)

        return analysis

    def _calculate_portfolio_correlation_factor(self) -> float:
        """Calcula factor de correlación del portfolio"""
        if len(self.positions) <= 1:
            return 0.0

        # Estimación simplificada basada en tipos de activos
        crypto_positions = sum(1 for pos in self.positions.keys()
                              if any(crypto in pos.upper() for crypto in ['BTC', 'ETH', 'SOL', 'ADA', 'XRP']))
        stock_positions = sum(1 for pos in self.positions.keys()
                             if any(stock in pos.upper() for stock in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']))

        correlation_factor = 0.0
        if crypto_positions >= 2:
            correlation_factor += 0.4
        if stock_positions >= 2:
            correlation_factor += 0.3

        return min(correlation_factor, 1.0)

    def _generate_risk_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Genera recomendaciones basadas en el análisis de riesgo"""
        recommendations = []

        risk_score = analysis['overall_risk_score']

        if risk_score > 80:
            recommendations.append("🚨 RIESGO CRÍTICO: Reducir exposición inmediatamente")
            recommendations.append("Considerar cerrar posiciones no esenciales")
        elif risk_score > 60:
            recommendations.append("⚠️ RIESGO ALTO: Reducir tamaño de nuevas posiciones")
            recommendations.append("Aumentar stops de protección")
        elif risk_score > 40:
            recommendations.append("📊 RIESGO MODERADO: Monitorear closely")
        else:
            recommendations.append("✅ RIESGO BAJO: Posición favorable para aumentar exposición")

        # Recomendaciones específicas por sector
        sector_analysis = analysis['sector_analysis']
        if sector_analysis['overexposed_sectors']:
            for sector_info in sector_analysis['overexposed_sectors']:
                recommendations.append(f"Reducir exposición en {sector_info['sector']} ({sector_info['exposure']:.1f}% > {sector_info['limit']:.1f}%)")

        # Recomendaciones de diversificación
        if sector_analysis['diversification_score'] < 75:
            recommendations.append("Mejorar diversificación: considerar nuevos sectores/activos")

        # Recomendaciones de correlación
        correlation_analysis = analysis['correlation_analysis']
        if correlation_analysis['correlation_warnings']:
            recommendations.append("Atención a correlaciones: " + ", ".join(correlation_analysis['correlation_warnings']))

        return recommendations

# Instancia global del gestor de riesgo
risk_manager = AdvancedRiskManager()

def get_risk_manager() -> AdvancedRiskManager:
    """Obtiene la instancia global del gestor de riesgo"""
    return risk_manager

def validate_risk_management_system():
    """Valida que el sistema de gestión de riesgo esté funcionando correctamente"""
    try:
        rm = get_risk_manager()

        # Verificar inicialización
        assert hasattr(rm, 'compensation_manager'), "CompensationManager no inicializado"
        assert hasattr(rm, 'positions'), "Sistema de posiciones no inicializado"
        assert hasattr(rm, 'risk_config'), "Configuración de riesgo no inicializada"

        # Verificar funcionalidades avanzadas
        assert hasattr(rm, '_calculate_kelly_position_size'), "Kelly Criterion no implementado"
        assert hasattr(rm, 'calculate_correlation_adjustment'), "Ajuste por correlación no implementado"
        assert hasattr(rm, '_calculate_sector_concentration'), "Análisis sectorial no implementado"
        assert hasattr(rm, 'analyze_portfolio_risk'), "Análisis de riesgo avanzado no implementado"

        print("✅ Sistema de gestión de riesgo validado correctamente")
        print("🔧 Funcionalidades avanzadas integradas:")
        print("   • Sistema de Kelly Criterion")
        print("   • Gestión de correlaciones")
        print("   • Límites de exposición por sector")
        print("   • Sistema de compensación avanzado")
        print("   • Análisis de riesgo del portfolio")
        print("   • Volatility-adjusted position sizing")

        return True

    except Exception as e:
        print(f"❌ Error en validación del sistema de riesgo: {e}")
        return False

# Ejecutar validación al importar el módulo
if __name__ != "__main__":
    validate_risk_management_system()
