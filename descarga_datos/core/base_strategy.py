#!/usr/bin/env python3
"""
Base Strategy - Clase Base para Estrategias de Trading
====================================================

Proporciona la estructura base y funcionalidades comunes
para todas las estrategias de trading del sistema.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import pandas as pd
import numpy as np

from .interfaces import IStrategy, TradingSignal, IOHLCVData

@dataclass
class Signal:
    """Señal de trading con información detallada"""
    symbol: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    timestamp: datetime
    confidence: float = 1.0
    strength: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class Position:
    """Posición de trading"""
    symbol: str
    entry_price: float
    quantity: float
    entry_time: datetime
    position_type: str  # 'long', 'short'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

class SignalType:
    """Tipos de señales estándar"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"

class BaseStrategy(IStrategy, ABC):
    """
    Clase base para todas las estrategias de trading.
    Proporciona funcionalidades comunes y estructura estándar.
    """

    def __init__(self, name: str, config: Optional[Any] = None):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

        # Estado de la estrategia
        self.positions: Dict[str, Position] = {}
        self.signals_history: List[Signal] = []
        self.performance_metrics: Dict[str, Any] = {}

        # Configuración por defecto
        self.min_signal_strength = getattr(config, 'min_signal_strength', 0.6) if config else 0.6
        self.max_positions = getattr(config, 'max_positions', 5) if config else 5
        self.position_size_percent = getattr(config, 'position_size_percent', 0.02) if config else 0.02

        # Estadísticas
        self.total_signals = 0
        self.profitable_signals = 0
        self.total_pnl = 0.0
        self.win_rate = 0.0

    @abstractmethod
    def generate_signals(self, data: IOHLCVData) -> List[Signal]:
        """
        Método abstracto que debe ser implementado por cada estrategia.
        Genera señales de trading basadas en los datos proporcionados.

        Args:
            data: Datos OHLCV del símbolo

        Returns:
            Lista de señales generadas
        """
        pass

    def calculate_position_size(self, signal: Signal, capital: float) -> float:
        """
        Calcula el tamaño de posición basado en la señal y capital disponible.

        Args:
            signal: Señal de trading
            capital: Capital disponible

        Returns:
            Tamaño de posición en unidades
        """
        try:
            # Tamaño base por porcentaje de capital
            position_value = capital * self.position_size_percent

            # Ajustar por fuerza de la señal
            strength_multiplier = max(0.5, min(2.0, signal.strength))

            # Ajustar por confianza
            confidence_multiplier = max(0.3, signal.confidence)

            adjusted_position_value = position_value * strength_multiplier * confidence_multiplier

            # Convertir a unidades del activo
            position_size = adjusted_position_value / signal.price

            # Limitar tamaño máximo
            max_position_size = capital * 0.1 / signal.price  # Máximo 10% del capital
            position_size = min(position_size, max_position_size)

            return position_size

        except Exception as e:
            self.logger.error(f"Error calculando tamaño de posición: {e}")
            return 0.0

    def validate_signal(self, signal: Signal) -> bool:
        """
        Valida si una señal cumple con los criterios mínimos.

        Args:
            signal: Señal a validar

        Returns:
            True si la señal es válida
        """
        # Verificar fuerza mínima de la señal
        if signal.strength < self.min_signal_strength:
            return False

        # Verificar que no exceda el máximo de posiciones
        if len(self.positions) >= self.max_positions:
            return False

        # Verificar que no haya una posición abierta en el mismo símbolo
        if signal.symbol in self.positions:
            return False

        return True

    def open_position(self, signal: Signal, quantity: float) -> bool:
        """
        Abre una nueva posición basada en la señal.

        Args:
            signal: Señal de trading
            quantity: Cantidad a operar

        Returns:
            True si la posición se abrió correctamente
        """
        try:
            if not self.validate_signal(signal):
                self.logger.warning(f"Señal inválida para {signal.symbol}")
                return False

            position = Position(
                symbol=signal.symbol,
                entry_price=signal.price,
                quantity=quantity,
                entry_time=signal.timestamp,
                position_type='long' if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY] else 'short'
            )

            self.positions[signal.symbol] = position
            self.signals_history.append(signal)
            self.total_signals += 1

            self.logger.info(f"Posición abierta: {signal.symbol} {position.position_type} {quantity} @ {signal.price}")
            return True

        except Exception as e:
            self.logger.error(f"Error abriendo posición: {e}")
            return False

    def close_position(self, symbol: str, exit_price: float, exit_time: datetime) -> Optional[float]:
        """
        Cierra una posición existente.

        Args:
            symbol: Símbolo de la posición a cerrar
            exit_price: Precio de salida
            exit_time: Tiempo de salida

        Returns:
            P&L de la operación cerrada, None si no hay posición
        """
        try:
            if symbol not in self.positions:
                return None

            position = self.positions[symbol]

            # Calcular P&L
            if position.position_type == 'long':
                pnl = (exit_price - position.entry_price) * position.quantity
            else:
                pnl = (position.entry_price - exit_price) * position.quantity

            # Actualizar estadísticas
            self.total_pnl += pnl
            if pnl > 0:
                self.profitable_signals += 1

            # Actualizar win rate
            if self.total_signals > 0:
                self.win_rate = self.profitable_signals / self.total_signals

            # Remover posición
            del self.positions[symbol]

            self.logger.info(f"Posición cerrada: {symbol} P&L: {pnl:.2f}")
            return pnl

        except Exception as e:
            self.logger.error(f"Error cerrando posición: {e}")
            return 0.0

    def get_open_positions(self) -> List[Position]:
        """Retorna todas las posiciones abiertas"""
        return list(self.positions.values())

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Retorna las métricas de rendimiento de la estrategia"""
        return {
            'total_signals': self.total_signals,
            'profitable_signals': self.profitable_signals,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'open_positions': len(self.positions),
            'avg_signal_strength': np.mean([s.strength for s in self.signals_history]) if self.signals_history else 0.0,
            'avg_confidence': np.mean([s.confidence for s in self.signals_history]) if self.signals_history else 0.0
        }

    def reset(self):
        """Reinicia el estado de la estrategia"""
        self.positions.clear()
        self.signals_history.clear()
        self.total_signals = 0
        self.profitable_signals = 0
        self.total_pnl = 0.0
        self.win_rate = 0.0
        self.logger.info("Estrategia reiniciada")

    def update_position_pnl(self, symbol: str, current_price: float):
        """
        Actualiza el P&L de una posición abierta.

        Args:
            symbol: Símbolo de la posición
            current_price: Precio actual del activo
        """
        try:
            if symbol in self.positions:
                position = self.positions[symbol]

                if position.position_type == 'long':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.quantity

                position.current_price = current_price

        except Exception as e:
            self.logger.error(f"Error actualizando P&L: {e}")

# === FUNCIONES DE UTILIDAD ===

def create_signal(symbol: str, signal_type: str, price: float, timestamp: datetime,
                 confidence: float = 1.0, strength: float = 0.0,
                 metadata: Optional[Dict[str, Any]] = None) -> Signal:
    """Crea una señal de trading"""
    return Signal(symbol, signal_type, price, timestamp, confidence, strength, metadata)

def calculate_returns(price_data: pd.Series) -> pd.Series:
    """Calcula los retornos de una serie de precios"""
    return price_data.pct_change().fillna(0)

def calculate_volatility(price_data: pd.Series, window: int = 20) -> pd.Series:
    """Calcula la volatilidad usando rolling std de retornos"""
    returns = calculate_returns(price_data)
    return returns.rolling(window=window).std() * np.sqrt(252)  # Annualized

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calcula el ratio de Sharpe"""
    try:
        excess_returns = returns - risk_free_rate / 252
        if excess_returns.std() == 0:
            return 0.0
        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
    except:
        return 0.0
