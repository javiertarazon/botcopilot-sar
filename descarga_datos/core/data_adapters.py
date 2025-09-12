"""
Adaptadores para manejar diferentes formatos de datos de exchanges.
Centraliza y optimiza la conversión entre formatos.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import logging
from .interfaces import IDataAdapter, IOHLCVData

class OHLCVData(IOHLCVData):
    """Implementación concreta de datos OHLCV"""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
    
    def get_dataframe(self) -> pd.DataFrame:
        return self.data.copy()
    
    def get_timeframe(self) -> str:
        """Detecta el timeframe basado en diferencias de timestamp"""
        if len(self.data) < 2:
            return "unknown"
        
        if 'timestamp' in self.data.columns:
            # Calcular diferencia promedio en segundos
            if pd.api.types.is_datetime64_any_dtype(self.data['timestamp']):
                diff_seconds = self.data['timestamp'].diff().dt.total_seconds().median()
            else:
                diff_seconds = self.data['timestamp'].diff().median()
            
            # Mapear a timeframes comunes
            if diff_seconds <= 60:
                return "1m"
            elif diff_seconds <= 300:
                return "5m"
            elif diff_seconds <= 900:
                return "15m"
            elif diff_seconds <= 3600:
                return "1h"
            elif diff_seconds <= 14400:
                return "4h"
            elif diff_seconds <= 86400:
                return "1d"
            else:
                return "1w"
        
        return "unknown"
    
    def validate(self) -> bool:
        """Validación básica de datos OHLCV"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in self.data.columns for col in required_columns)

class CCXTAdapter(IDataAdapter):
    """Adaptador para datos de CCXT"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def adapt_ohlcv(self, raw_data: List[List], symbol: str, timeframe: str) -> IOHLCVData:
        """
        Convierte datos OHLCV de CCXT a formato estandarizado.
        
        Args:
            raw_data: Lista de listas [timestamp, open, high, low, close, volume]
            symbol: Símbolo del trading pair
            timeframe: Timeframe de los datos
            
        Returns:
            IOHLCVData: Datos en formato estandarizado
        """
        if not raw_data:
            return OHLCVData(pd.DataFrame())
        
        try:
            # Convertir a DataFrame
            df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convertir tipos de datos
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            # Agregar metadatos
            df['symbol'] = symbol
            df['timeframe'] = timeframe
            
            # Limpiar datos
            df = self._clean_ohlcv_data(df)
            
            self.logger.info(f"Adaptados {len(df)} registros OHLCV para {symbol} {timeframe}")
            return OHLCVData(df)
            
        except Exception as e:
            self.logger.error(f"Error adaptando datos CCXT: {e}")
            return OHLCVData(pd.DataFrame())
    
    def _clean_ohlcv_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia y valida datos OHLCV"""
        original_len = len(df)
        
        # Eliminar filas con valores nulos en columnas críticas
        critical_columns = ['open', 'high', 'low', 'close']
        df = df.dropna(subset=critical_columns)
        
        # Eliminar filas con precios <= 0
        price_mask = (df[critical_columns] > 0).all(axis=1)
        df = df[price_mask]
        
        # Validar relación high >= low
        valid_hl = df['high'] >= df['low']
        df = df[valid_hl]
        
        # Validar que open y close están entre high y low
        valid_range = (
            (df['open'] <= df['high']) & 
            (df['open'] >= df['low']) & 
            (df['close'] <= df['high']) & 
            (df['close'] >= df['low'])
        )
        df = df[valid_range]
        
        # Ordenar por timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        cleaned_len = len(df)
        if cleaned_len < original_len:
            self.logger.warning(f"Datos limpiados: {original_len} -> {cleaned_len} registros")
        
        return df

class DataFrameAdapter(IDataAdapter):
    """Adaptador para DataFrames existentes"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def adapt_ohlcv(self, data: pd.DataFrame, symbol: str = None, timeframe: str = None) -> IOHLCVData:
        """
        Adapta un DataFrame existente al formato OHLCV estandarizado.
        
        Args:
            data: DataFrame con datos OHLCV
            symbol: Símbolo opcional (se agrega si no existe)
            timeframe: Timeframe opcional (se agrega si no existe)
            
        Returns:
            IOHLCVData: Datos en formato estandarizado
        """
        if data.empty:
            return OHLCVData(pd.DataFrame())
        
        try:
            df = data.copy()
            
            # Normalizar nombres de columnas
            df = self._normalize_column_names(df)
            
            # Convertir timestamp si es necesario
            df = self._normalize_timestamp(df)
            
            # Agregar metadatos si no existen
            if 'symbol' not in df.columns and symbol:
                df['symbol'] = symbol
            if 'timeframe' not in df.columns and timeframe:
                df['timeframe'] = timeframe
            
            self.logger.info(f"Adaptado DataFrame con {len(df)} registros")
            return OHLCVData(df)
            
        except Exception as e:
            self.logger.error(f"Error adaptando DataFrame: {e}")
            return OHLCVData(pd.DataFrame())
    
    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nombres de columnas a formato estándar"""
        column_mapping = {
            'Open': 'open', 'OPEN': 'open',
            'High': 'high', 'HIGH': 'high',
            'Low': 'low', 'LOW': 'low',
            'Close': 'close', 'CLOSE': 'close',
            'Volume': 'volume', 'VOLUME': 'volume',
            'Timestamp': 'timestamp', 'TIMESTAMP': 'timestamp',
            'Date': 'timestamp', 'DATE': 'timestamp',
            'DateTime': 'timestamp', 'DATETIME': 'timestamp'
        }
        
        return df.rename(columns=column_mapping)
    
    def _normalize_timestamp(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza columna timestamp"""
        if 'timestamp' not in df.columns:
            if df.index.name in ['timestamp', 'Date', 'DateTime']:
                df = df.reset_index()
                df = df.rename(columns={df.columns[0]: 'timestamp'})
            elif pd.api.types.is_datetime64_any_dtype(df.index):
                df = df.reset_index()
                df = df.rename(columns={df.columns[0]: 'timestamp'})
        
        if 'timestamp' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                # Intentar convertir a datetime
                try:
                    # Intentar como Unix timestamp en segundos
                    if pd.api.types.is_numeric_dtype(df['timestamp']):
                        # Determinar si son segundos o milisegundos
                        max_ts = df['timestamp'].max()
                        if max_ts > 1e10:  # Milisegundos
                            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                        else:  # Segundos
                            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                    else:
                        # Intentar parseo automático
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                except Exception as e:
                    self.logger.warning(f"No se pudo convertir timestamp: {e}")
        
        return df

class AdapterFactory:
    """Factory para crear adaptadores apropiados"""
    
    @staticmethod
    def create_adapter(data_source: str, logger: Optional[logging.Logger] = None) -> IDataAdapter:
        """
        Crea el adaptador apropiado según la fuente de datos.
        
        Args:
            data_source: Tipo de fuente ('ccxt', 'dataframe', etc.)
            logger: Logger opcional
            
        Returns:
            IDataAdapter: Adaptador apropiado
        """
        if data_source.lower() == 'ccxt':
            return CCXTAdapter(logger)
        elif data_source.lower() in ['dataframe', 'csv', 'pandas']:
            return DataFrameAdapter(logger)
        else:
            # Por defecto, usar adaptador de DataFrame
            return DataFrameAdapter(logger)
