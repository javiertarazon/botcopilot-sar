"""
Validador de datos centralizado y optimizado.
Elimina duplicaciones de validación en múltiples módulos.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
from .interfaces import IDataValidator

@dataclass
class ValidationResult:
    """Resultado de validación estandarizado"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any] = None

# Alias para compatibilidad con código existente
DataValidationResult = ValidationResult

class DataValidator(IDataValidator):
    """Validador de datos centralizado y optimizado"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    """Validador de datos centralizado y optimizado"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def validate_ohlcv_data(self, data: pd.DataFrame) -> ValidationResult:
        """
        Valida datos OHLCV básicos.
        
        Args:
            data: DataFrame con datos OHLCV
            
        Returns:
            ValidationResult: Resultado de la validación
        """
        errors = []
        warnings = []
        
        # 1. Verificar que el DataFrame no está vacío
        if data.empty:
            errors.append("El DataFrame está vacío")
            return ValidationResult(False, errors, warnings)
        
        # 2. Verificar columnas OHLCV requeridas
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            errors.append(f"Faltan columnas OHLCV requeridas: {missing_columns}")
        
        # 3. Verificar valores nulos en columnas críticas
        if not missing_columns:  # Solo si tenemos las columnas
            null_check = data[required_columns].isnull().any()
            if null_check.any():
                null_cols = null_check[null_check].index.tolist()
                errors.append(f"Valores nulos en columnas OHLCV: {null_cols}")
        
        # 4. Verificar validez de precios
        if 'open' in data.columns and 'high' in data.columns and 'low' in data.columns and 'close' in data.columns:
            price_columns = ['open', 'high', 'low', 'close']
            
            # 4.1 Verificar precios positivos
            negative_prices = (data[price_columns] <= 0).any().any()
            if negative_prices:
                errors.append("Hay precios negativos o cero en los datos")
            
            # 4.2 Verificar relación high-low
            invalid_hl = (data['high'] < data['low']).sum()
            if invalid_hl > 0:
                errors.append(f"Hay {invalid_hl} registros donde high < low")
            
            # 4.3 Verificar que open/close están entre high y low
            price_logic = (
                (data['open'] <= data['high']) & 
                (data['open'] >= data['low']) & 
                (data['close'] <= data['high']) & 
                (data['close'] >= data['low'])
            )
            invalid_logic = (~price_logic).sum()
            if invalid_logic > 0:
                errors.append(f"Hay {invalid_logic} registros con precios open/close fuera del rango high-low")
        
        # 5. Verificar volumen
        if 'volume' in data.columns:
            negative_volume = (data['volume'] < 0).sum()
            if negative_volume > 0:
                errors.append(f"Hay {negative_volume} valores negativos en el volumen")
        
        # 6. Warnings para datos sospechosos
        if not errors and len(data) < 100:
            warnings.append(f"Dataset muy pequeño: solo {len(data)} registros")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def validate_trading_data(self, data: pd.DataFrame) -> ValidationResult:
        """
        Valida datos para trading (OHLCV + indicadores técnicos).
        
        Args:
            data: DataFrame con datos OHLCV e indicadores
            
        Returns:
            ValidationResult: Resultado de la validación
        """
        # Primero validar OHLCV
        ohlcv_result = self.validate_ohlcv_data(data)
        if not ohlcv_result.is_valid:
            return ohlcv_result
        
        errors = ohlcv_result.errors.copy()
        warnings = ohlcv_result.warnings.copy()
        
        # Verificar indicadores técnicos requeridos para trading
        technical_columns = ['sar', 'atr', 'adx']
        missing_tech = [col for col in technical_columns if col not in data.columns]
        if missing_tech:
            errors.append(f"Faltan indicadores técnicos: {missing_tech}")
        
        # Verificar indicadores técnicos
        if not missing_tech:
            # Verificar valores nulos en indicadores (algunos pueden tener NaN al inicio)
            tech_nulls = data[technical_columns].isnull().sum()
            for col, null_count in tech_nulls.items():
                if null_count > len(data) * 0.1:  # Más del 10% nulos
                    warnings.append(f"Indicador {col} tiene {null_count} valores nulos ({null_count/len(data)*100:.1f}%)")
        
        # Verificar timestamp si existe
        if 'timestamp' in data.columns:
            if data['timestamp'].dtype not in ['datetime64[ns]', 'int64']:
                errors.append("Columna timestamp debe ser datetime o int64")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def validate_strategy_requirements(self, data: pd.DataFrame, strategy_name: str) -> ValidationResult:
        """
        Valida requisitos específicos de una estrategia.
        
        Args:
            data: DataFrame con datos
            strategy_name: Nombre de la estrategia
            
        Returns:
            ValidationResult: Resultado de la validación
        """
        errors = []
        warnings = []
        
        if strategy_name.lower() == 'utbot_psar':
            required_cols = ['open', 'high', 'low', 'close', 'volume', 'atr', 'sar', 'ema_10', 'ema_200']
            missing = [col for col in required_cols if col not in data.columns]
            if missing:
                errors.append(f"Estrategia {strategy_name} requiere columnas: {missing}")
                
            # Verificar que tenemos suficientes datos para EMA_200
            if len(data) < 250:
                warnings.append(f"Dataset pequeño para EMA_200: {len(data)} registros (recomendado: >250)")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def validate_timestamp_column(self, data: pd.DataFrame) -> ValidationResult:
        """Valida específicamente la columna timestamp"""
        errors = []
        warnings = []
        
        if 'timestamp' not in data.columns:
            errors.append("Falta columna timestamp")
            return ValidationResult(False, errors, warnings)
        
        # Verificar tipo de datos
        if not pd.api.types.is_datetime64_any_dtype(data['timestamp']) and not pd.api.types.is_integer_dtype(data['timestamp']):
            errors.append("Timestamp debe ser datetime o integer")
        
        # Verificar orden cronológico
        if len(data) > 1:
            if pd.api.types.is_datetime64_any_dtype(data['timestamp']):
                is_sorted = data['timestamp'].is_monotonic_increasing
            else:
                is_sorted = data['timestamp'].is_monotonic_increasing
                
            if not is_sorted:
                warnings.append("Los timestamps no están en orden cronológico")
        
        return ValidationResult(len(errors) == 0, errors, warnings)

    def validate_data(self, data: Any) -> ValidationResult:
        """Método de compatibilidad con BaseDataHandler"""
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={"source": "compatibility"}
        )

    def process_data(self, data: Any) -> Any:
        """Método de compatibilidad con BaseDataHandler"""
        return data
