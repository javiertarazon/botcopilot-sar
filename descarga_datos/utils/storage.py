"""
Módulo de compatibilidad para almacenamiento de datos.
Proporciona interfaces compatibles con el código existente mientras
utiliza el sistema de almacenamiento unificado internamente.
"""
import sqlite3
import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Union, List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

# Importar desde el sistema unificado
from core.unified_storage import UnifiedDataStorage
from core.config_manager import StorageConfig
from core.base_data_handler import BaseDataHandler, DataValidationResult

logger = logging.getLogger(__name__)

@dataclass
class Trade:
    """Clase para representar una operación de trading"""
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    side: str = 'long'  # 'long' o 'short'
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    is_compensation: bool = False
    original_loss_amount: float = 0.0
    compensation_multiplier: float = 1.0
    status: str = 'open'  # 'open', 'closed', 'compensated'

class DataStorage(BaseDataHandler):
    """Clase de compatibilidad que envuelve UnifiedDataStorage"""

    def __init__(self, db_path: str = "data/data.db"):
        super().__init__()
        # Crear configuración de almacenamiento básica
        self.db_path = db_path
        self._ensure_db_path()

        # Configurar UnifiedDataStorage
        storage_config = StorageConfig(
            sqlite_path=db_path,
            csv_path=str(Path(db_path).parent / "csv_data")
        )
        self._unified_storage = UnifiedDataStorage(storage_config)

    def _ensure_db_path(self):
        """Asegura que el directorio de la base de datos existe."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def validate_timestamp_column(self, df: pd.DataFrame) -> DataValidationResult:
        """
        Valida la columna de timestamp en el DataFrame.

        Args:
            df: DataFrame a validar

        Returns:
            DataValidationResult con el resultado de la validación
        """
        errors = []
        warnings = []

        # Verificar que existe columna timestamp
        if 'timestamp' not in df.columns:
            errors.append("Columna 'timestamp' no encontrada")
            return DataValidationResult(False, errors, warnings)

        # Verificar que no hay valores nulos
        null_count = df['timestamp'].isnull().sum()
        if null_count > 0:
            errors.append(f"Columna 'timestamp' tiene {null_count} valores nulos")

        # Verificar que los valores son válidos
        try:
            ts_series = pd.to_datetime(df['timestamp'], errors='coerce')
            invalid_count = ts_series.isnull().sum()
            if invalid_count > 0:
                errors.append(f"Columna 'timestamp' tiene {invalid_count} valores inválidos")
        except Exception as e:
            errors.append(f"Error convirtiendo timestamps: {e}")

        # Verificar orden temporal
        if len(df) > 1:
            is_sorted = df['timestamp'].is_monotonic_increasing
            if not is_sorted:
                warnings.append("Los timestamps no están en orden ascendente")

        return DataValidationResult(len(errors) == 0, errors, warnings)

    def save_to_sqlite(self, data: Union[pd.DataFrame, List[Dict[str, Any]]],
                      table_name: str,
                      validate: bool = True) -> bool:
        """Guarda datos en SQLite usando el sistema unificado"""
        try:
            return self._unified_storage.save_data(data, table_name, validate)
        except Exception as e:
            logger.error(f"Error guardando en SQLite: {e}")
            return False

    def query_data(self, query: str, params: Optional[tuple] = None) -> Optional[pd.DataFrame]:
        """Consulta datos usando el sistema unificado"""
        try:
            return self._unified_storage.query_data(query, params)
        except Exception as e:
            logger.error(f"Error consultando datos: {e}")
            return None

class SimpleStorage:
    """Clase simple para almacenamiento de datos (compatibilidad)"""

    def __init__(self, db_path: str = "data/data.db"):
        self.db_path = db_path
        self._ensure_db_path()

    def _ensure_db_path(self):
        """Asegura que el directorio de la base de datos existe."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

def save_to_csv(data: Union[pd.DataFrame, List[Dict[str, Any]]],
              filepath: str,
              storage: Optional[DataStorage] = None) -> bool:
    """
    Guarda datos en CSV con manejo consistente de timestamps.

    Args:
        data: DataFrame o lista de diccionarios con los datos
        filepath: Ruta del archivo CSV
        storage: Instancia opcional de DataStorage para validación

    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Convertir a DataFrame si es necesario
        df = pd.DataFrame(data) if isinstance(data, list) else data.copy()

        # Validar si hay storage
        if storage:
            validation_result = storage.validate_timestamp_column(df)
            if not validation_result.is_valid:
                logger.error("Datos inválidos para guardar en CSV")
                return False

        # Crear directorio si no existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Guardar en CSV
        df.to_csv(filepath, index=False)
        logger.info(f"Data saved to CSV: {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error guardando datos en CSV: {str(e)}")
        return False
