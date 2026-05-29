"""
Data normalization module for machine learning preprocessing.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from config.config import NormalizationConfig

logger = logging.getLogger(__name__)

try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    StandardScaler = MinMaxScaler = RobustScaler = None
    _SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn no disponible, normalización en modo no-op")


class _IdentityScaler:
    def fit(self, X):
        return self

    def transform(self, X):
        return X

    def inverse_transform(self, X):
        return X


class DataNormalizer:
    """
    Class for normalizing and scaling financial data for machine learning.
    """
    
    def __init__(self, config: NormalizationConfig = None):
        """
        Initialize the data normalizer.
        
        Args:
            config (NormalizationConfig): Configuration for scaling
        """
        self.config = config or NormalizationConfig()
        self.scalers: Dict[str, any] = {}
        self.feature_names: List[str] = []
        self.is_fitted = False
        
        # Definir el orden correcto de las columnas
        self.column_order = [
            'timestamp',  # timestamp siempre primero y no se normaliza
            'open', 'high', 'low', 'close', 'volume',  # OHLCV básico
            'ha_open', 'ha_high', 'ha_low', 'ha_close', 'ha_trend',  # Heiken Ashi
            'volatility', 'atr', 'adx',  # Indicadores
            'ema_10', 'ema_20', 'ema_200',  # EMAs
            'sar'  # SAR
        ]
    
    def fit(self, data: pd.DataFrame, features: Optional[List[str]] = None):
        """
        Fit the scaler to the data.
        
        Args:
            data (pd.DataFrame): Input data to fit
            features (List[str]): List of features to scale. If None, uses all numeric columns except timestamp.
        """
        if features is None:
            # Usar todas las columnas del orden predefinido excepto timestamp
            features = [col for col in self.column_order if col != 'timestamp' and col in data.columns]
        
        self.feature_names = features
        logger.info(f"Normalizing features: {features}")
        
        for feature in features:
            if feature not in data.columns:
                logger.warning(f"Feature '{feature}' not found in data, skipping")
                continue
                
            # Inicializar el escalador según la configuración
            if not _SKLEARN_AVAILABLE:
                scaler = _IdentityScaler()
            else:
                if self.config.method.lower() == "standard":
                    scaler = StandardScaler(with_mean=self.config.with_mean, with_std=self.config.with_std)
                elif self.config.method.lower() == "minmax":
                    scaler = MinMaxScaler(feature_range=self.config.feature_range)
                elif self.config.method.lower() == "robust":
                    scaler = RobustScaler(quantile_range=self.config.quantile_range)
                else:
                    scaler = MinMaxScaler(feature_range=self.config.feature_range)  # Por defecto
            
            # Ajustar el escalador con los datos no nulos
            feature_data = data[feature].values.reshape(-1, 1)
            mask = ~np.isnan(feature_data.flatten())
            if np.any(mask):
                scaler.fit(feature_data[mask])
                self.scalers[feature] = scaler
        
        self.is_fitted = True
    
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Transform the data using fitted scalers and maintain column order.
        
        Args:
            data (pd.DataFrame): Data to transform
            
        Returns:
            pd.DataFrame: Transformed data with ordered columns
        """
        if not self.is_fitted:
            raise RuntimeError("Scaler must be fitted before transformation")
        
        # Crear un DataFrame vacío con el mismo índice
        result = pd.DataFrame(index=data.index)
        
        # Primero copiar el timestamp sin transformar, asegurando que esté en formato Unix timestamp
        if 'timestamp' in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data['timestamp']):
                result['timestamp'] = data['timestamp'].astype(np.int64) // 10**9
            else:
                # Si ya es un número, asumimos que está en segundos
                result['timestamp'] = data['timestamp']
        
        # Normalizar todas las columnas numéricas según el orden predefinido
        for feature in self.column_order:
            if feature == 'timestamp' or feature not in data.columns:
                continue
                
            if feature in self.scalers:
                # Aplicar normalización
                feature_data = data[feature].values.reshape(-1, 1)
                mask = ~np.isnan(feature_data.flatten())
                
                if np.any(mask):
                    transformed_values = np.full_like(feature_data, np.nan)
                    transformed_values[mask] = self.scalers[feature].transform(feature_data[mask])
                    result[feature] = transformed_values.flatten()
            else:
                # Si la columna no tiene scaler, copiarla sin transformar
                result[feature] = data[feature]
        
        # Asegurar que las columnas estén en el orden correcto
        ordered_columns = [col for col in self.column_order if col in result.columns]
        result = result[ordered_columns]
        
        return result
    
    def fit_transform(self, data: pd.DataFrame, features: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Fit and transform the data.
        
        Args:
            data (pd.DataFrame): Data to fit and transform
            features (List[str]): Features to scale
            
        Returns:
            pd.DataFrame: Transformed data
        """
        self.fit(data, features)
        return self.transform(data)
    
    def inverse_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Inverse transform the data.
        
        Args:
            data (pd.DataFrame): Transformed data to invert
            
        Returns:
            pd.DataFrame: Original scale data
        """
        if not self.is_fitted:
            raise RuntimeError("Scaler must be fitted before inverse transformation")
        
        result = pd.DataFrame(index=data.index)
        
        # Manejar el timestamp primero
        if 'timestamp' in data.columns:
            if pd.api.types.is_integer_dtype(data['timestamp']):
                # Si es un entero, asumimos que está en segundos Unix
                result['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')
            else:
                # Si no es entero, intentar convertir a datetime
                result['timestamp'] = pd.to_datetime(data['timestamp'])
        
        # Procesar el resto de las columnas
        for feature, scaler in self.scalers.items():
            if feature not in data.columns:
                continue
            
            # Manejar valores faltantes
            feature_data = data[feature].values.reshape(-1, 1)
            mask = ~np.isnan(feature_data.flatten())
            
            if np.any(mask):
                original_values = np.full_like(feature_data, np.nan)
                original_values[mask] = scaler.inverse_transform(feature_data[mask])
                result[feature] = original_values.flatten()
            else:
                result[feature] = data[feature]
        
        # Copiar cualquier columna no transformada
        for col in data.columns:
            if col not in result.columns and col != 'timestamp':
                result[col] = data[col]
        
        # Asegurar que las columnas estén en el orden correcto
        ordered_columns = [col for col in self.column_order if col in result.columns]
        result = result[ordered_columns]
        
        return result
