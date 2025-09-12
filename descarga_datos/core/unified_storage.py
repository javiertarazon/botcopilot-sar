"""
Storage unificado que elimina duplicaciones y optimiza el acceso a datos.
Implementa interfaces limpias y manejo de errores robusto.
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
import logging
from datetime import datetime, timedelta
import json

from .interfaces import IDataStorage, IOHLCVData
from .config_manager import StorageConfig
from .data_validator import DataValidator, ValidationResult

class UnifiedDataStorage(IDataStorage):
    """Storage unificado que maneja SQLite y CSV de forma optimizada"""
    
    def __init__(self, storage_config: StorageConfig, logger: Optional[logging.Logger] = None):
        self.config = storage_config
        self.logger = logger or logging.getLogger(__name__)
        self.validator = DataValidator(self.logger)

        # Configurar rutas con valores por defecto si no existen
        sqlite_path = getattr(storage_config, 'sqlite_path', 'data/market_data.db') if storage_config else 'data/market_data.db'
        csv_path = getattr(storage_config, 'csv_path', 'data/csv') if storage_config else 'data/csv'
        enable_sqlite = getattr(storage_config, 'enable_sqlite', True) if storage_config else True
        enable_csv = getattr(storage_config, 'enable_csv', True) if storage_config else True

        self.sqlite_path = Path(sqlite_path)
        self.csv_path = Path(csv_path)
        self.enable_sqlite = enable_sqlite
        self.enable_csv = enable_csv
        
        # Conexión SQLite
        self._connection: Optional[sqlite3.Connection] = None
        
        # Cache de esquemas de tablas
        self._table_schemas: Dict[str, List[str]] = {}
        
        # Estadísticas
        self.storage_stats = {
            'sqlite_writes': 0,
            'csv_writes': 0,
            'sqlite_reads': 0,
            'csv_reads': 0,
            'errors': 0
        }
    
    def get_connection(self) -> sqlite3.Connection:
        """Obtiene conexión SQLite con manejo de reconexión"""
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(
                    self.sqlite_path,
                    timeout=30.0,
                    check_same_thread=False
                )
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=NORMAL")
                self._connection.execute("PRAGMA cache_size=10000")
                self._connection.execute("PRAGMA temp_store=MEMORY")
                
                self.logger.info(f"Conexión SQLite establecida: {self.sqlite_path}")
                
            except Exception as e:
                self.logger.error(f"Error conectando a SQLite: {e}")
                raise
        
        return self._connection
    
    def save_ohlcv_data(self, symbol: str, timeframe: str, data: IOHLCVData) -> bool:
        """
        Guarda datos OHLCV en SQLite y/o CSV según configuración.
        
        Args:
            symbol: Símbolo del trading pair
            timeframe: Intervalo de tiempo
            data: Datos OHLCV a guardar
            
        Returns:
            bool: True si se guardó exitosamente
        """
        df = data.get_dataframe()
        
        if df.empty:
            self.logger.warning(f"DataFrame vacío para {symbol} {timeframe}")
            return False
        
        # Validar datos antes de guardar
        validation = self.validator.validate_ohlcv_data(df)
        if not validation.is_valid:
            self.logger.error(f"Datos inválidos para {symbol}: {validation.errors}")
            self.storage_stats['errors'] += 1
            return False
        
        success = True
        
        # Preparar datos para storage
        df_processed = self._prepare_dataframe_for_storage(df, symbol, timeframe)
        
        # Guardar en SQLite si está habilitado
        if self.config.enable_sqlite:
            success &= self._save_to_sqlite(symbol, timeframe, df_processed)
        
        # Guardar en CSV si está habilitado
        if self.config.enable_csv:
            success &= self._save_to_csv(symbol, timeframe, df_processed)
        
        return success
    
    def load_ohlcv_data(self, symbol: str, timeframe: str, 
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Carga datos OHLCV desde el storage.
        
        Args:
            symbol: Símbolo del trading pair
            timeframe: Intervalo de tiempo
            start_date: Fecha inicial (YYYY-MM-DD)
            end_date: Fecha final (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: Datos cargados o None si no existen
        """
        # Intentar cargar desde SQLite primero (más rápido)
        if self.config.enable_sqlite:
            data = self._load_from_sqlite(symbol, timeframe, start_date, end_date)
            if data is not None and not data.empty:
                self.storage_stats['sqlite_reads'] += 1
                return data
        
        # Fallback a CSV
        if self.config.enable_csv:
            data = self._load_from_csv(symbol, timeframe, start_date, end_date)
            if data is not None and not data.empty:
                self.storage_stats['csv_reads'] += 1
                return data
        
        self.logger.warning(f"No se encontraron datos para {symbol} {timeframe}")
        return None
    
    def data_exists(self, symbol: str, timeframe: str) -> bool:
        """Verifica si existen datos para un símbolo y timeframe"""
        # Verificar en SQLite primero
        if self.config.enable_sqlite:
            try:
                table_name = self._get_table_name(symbol, timeframe)
                conn = self.get_connection()
                
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                
                if cursor.fetchone():
                    # Verificar que la tabla tiene datos
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    return count > 0
                    
            except Exception as e:
                self.logger.debug(f"Error verificando SQLite: {e}")
        
        # Verificar en CSV
        if self.config.enable_csv:
            csv_file = self._get_csv_filename(symbol, timeframe, base_only=True)
            return csv_file.exists()
        
        return False
    
    def get_data_range(self, symbol: str, timeframe: str) -> Optional[Tuple[datetime, datetime]]:
        """Obtiene el rango de fechas disponible para un símbolo"""
        try:
            if self.config.enable_sqlite:
                table_name = self._get_table_name(symbol, timeframe)
                conn = self.get_connection()
                
                cursor = conn.execute(f"""
                    SELECT MIN(timestamp), MAX(timestamp) 
                    FROM {table_name}
                """)
                
                result = cursor.fetchone()
                if result and result[0] and result[1]:
                    min_ts = pd.to_datetime(result[0], unit='s')
                    max_ts = pd.to_datetime(result[1], unit='s')
                    return min_ts, max_ts
                    
        except Exception as e:
            self.logger.debug(f"Error obteniendo rango de datos: {e}")
        
        return None
    
    def cleanup_old_data(self, days_to_keep: int = 365) -> bool:
        """Limpia datos antiguos del storage"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_timestamp = int(cutoff_date.timestamp())
            
            if self.config.enable_sqlite:
                conn = self.get_connection()
                
                # Obtener todas las tablas
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    try:
                        conn.execute(
                            f"DELETE FROM {table} WHERE timestamp < ?",
                            (cutoff_timestamp,)
                        )
                    except Exception as e:
                        self.logger.warning(f"Error limpiando tabla {table}: {e}")
                
                conn.commit()
                self.logger.info(f"Datos anteriores a {cutoff_date.date()} eliminados")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error limpiando datos antiguos: {e}")
            return False
    
    def _save_to_sqlite(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Guarda DataFrame en SQLite"""
        try:
            table_name = self._get_table_name(symbol, timeframe)
            conn = self.get_connection()
            
            # Crear tabla si no existe
            self._ensure_table_exists(table_name, df)
            
            # Convertir timestamp a int64 para SQLite
            df_sqlite = df.copy()
            if 'timestamp' in df_sqlite.columns:
                if pd.api.types.is_datetime64_any_dtype(df_sqlite['timestamp']):
                    df_sqlite['timestamp'] = df_sqlite['timestamp'].astype('int64') // 10**9
            
            # Usar REPLACE para evitar duplicados
            df_sqlite.to_sql(table_name, conn, if_exists='replace', index=False)
            conn.commit()
            
            self.storage_stats['sqlite_writes'] += 1
            self.logger.debug(f"Guardados {len(df)} registros en SQLite para {symbol} {timeframe}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error guardando en SQLite: {e}")
            self.storage_stats['errors'] += 1
            return False
    
    def _save_to_csv(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Guarda DataFrame en CSV"""
        try:
            csv_file = self._get_csv_filename(symbol, timeframe)
            
            # Asegurar que el directorio existe
            csv_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Guardar con formato optimizado
            df.to_csv(csv_file, index=False, float_format='%.8f')
            
            self.storage_stats['csv_writes'] += 1
            self.logger.debug(f"Guardados {len(df)} registros en CSV: {csv_file.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error guardando en CSV: {e}")
            self.storage_stats['errors'] += 1
            return False
    
    def _load_from_sqlite(self, symbol: str, timeframe: str,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Carga datos desde SQLite"""
        try:
            table_name = self._get_table_name(symbol, timeframe)
            conn = self.get_connection()
            
            # Construir query con filtros de fecha opcionales
            query = f"SELECT * FROM {table_name}"
            params = []
            
            if start_date or end_date:
                conditions = []
                
                if start_date:
                    start_ts = int(pd.to_datetime(start_date).timestamp())
                    conditions.append("timestamp >= ?")
                    params.append(start_ts)
                
                if end_date:
                    end_ts = int(pd.to_datetime(end_date).timestamp())
                    conditions.append("timestamp <= ?")
                    params.append(end_ts)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY timestamp"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                df = self._postprocess_dataframe(df)
            
            return df
            
        except Exception as e:
            self.logger.debug(f"Error cargando desde SQLite: {e}")
            return None
    
    def _load_from_csv(self, symbol: str, timeframe: str,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Carga datos desde CSV"""
        try:
            csv_file = self._get_csv_filename(symbol, timeframe, base_only=True)
            
            if not csv_file.exists():
                return None
            
            df = pd.read_csv(csv_file)
            
            if df.empty:
                return None
            
            # Aplicar filtros de fecha si se especifican
            if start_date or end_date:
                df = self._postprocess_dataframe(df)
                
                if start_date:
                    start_dt = pd.to_datetime(start_date)
                    df = df[df['timestamp'] >= start_dt]
                
                if end_date:
                    end_dt = pd.to_datetime(end_date)
                    df = df[df['timestamp'] <= end_dt]
            else:
                df = self._postprocess_dataframe(df)
            
            return df
            
        except Exception as e:
            self.logger.debug(f"Error cargando desde CSV: {e}")
            return None
    
    def _prepare_dataframe_for_storage(self, df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
        """Prepara DataFrame para almacenamiento"""
        df_clean = df.copy()
        
        # Asegurar columnas básicas
        if 'symbol' not in df_clean.columns:
            df_clean['symbol'] = symbol
        if 'timeframe' not in df_clean.columns:
            df_clean['timeframe'] = timeframe
        
        # Normalizar timestamp
        if 'timestamp' in df_clean.columns:
            if pd.api.types.is_datetime64_any_dtype(df_clean['timestamp']):
                # Mantener como datetime para CSV, convertir en _save_to_sqlite si es necesario
                pass
            else:
                # Convertir a datetime si es numérico
                df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'], unit='s')
        
        # Ordenar por timestamp
        if 'timestamp' in df_clean.columns:
            df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)
        
        # Eliminar duplicados
        duplicate_cols = ['timestamp']
        if 'symbol' in df_clean.columns:
            duplicate_cols.append('symbol')
        
        df_clean = df_clean.drop_duplicates(subset=duplicate_cols, keep='last')
        
        return df_clean
    
    def _postprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Post-procesa DataFrame después de carga"""
        if df.empty:
            return df
        
        # Convertir timestamp a datetime si es necesario
        if 'timestamp' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                if pd.api.types.is_integer_dtype(df['timestamp']):
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Asegurar tipos de datos correctos para columnas numéricas
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def _get_table_name(self, symbol: str, timeframe: str) -> str:
        """Genera nombre de tabla SQLite"""
        # Limpiar caracteres especiales
        clean_symbol = symbol.replace('/', '_').replace('-', '_')
        return f"{clean_symbol}_{timeframe}_ohlcv"
    
    def _get_csv_filename(self, symbol: str, timeframe: str, base_only: bool = False) -> Path:
        """Genera nombre de archivo CSV"""
        clean_symbol = symbol.replace('/', '_')
        # Usar nombre genérico para exchange ya que StorageConfig no tiene exchange
        filename = f"trading_{clean_symbol}_{timeframe}_ohlcv.csv"
        
        if base_only:
            # Buscar archivos existentes con patrón similar
            pattern = f"*{clean_symbol}_{timeframe}_ohlcv*.csv"
            existing_files = list(self.csv_path.glob(pattern))
            if existing_files:
                return existing_files[0]
        
        return self.csv_path / filename
    
    def _ensure_table_exists(self, table_name: str, df: pd.DataFrame):
        """Asegura que la tabla SQLite existe con el esquema correcto"""
        if table_name in self._table_schemas:
            return
        
        try:
            conn = self.get_connection()
            
            # Verificar si la tabla existe
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            
            if not cursor.fetchone():
                # Crear tabla con esquema basado en el DataFrame
                self._create_table_schema(table_name, df)
            
            self._table_schemas[table_name] = list(df.columns)
            
        except Exception as e:
            self.logger.error(f"Error creando tabla {table_name}: {e}")
            raise
    
    def _create_table_schema(self, table_name: str, df: pd.DataFrame):
        """Crea esquema de tabla SQLite basado en DataFrame"""
        conn = self.get_connection()
        
        # Mapear tipos de pandas a SQLite
        type_mapping = {
            'int64': 'INTEGER',
            'float64': 'REAL',
            'object': 'TEXT',
            'datetime64[ns]': 'INTEGER',  # Almacenar como timestamp
            'bool': 'INTEGER'
        }
        
        columns = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            sql_type = type_mapping.get(dtype, 'TEXT')
            
            # Timestamp como clave primaria
            if col == 'timestamp':
                columns.append(f"{col} {sql_type} PRIMARY KEY")
            else:
                columns.append(f"{col} {sql_type}")
        
        create_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
        
        conn.execute(create_sql)
        conn.commit()
        
        self.logger.info(f"Tabla {table_name} creada exitosamente")
    
    # Métodos de compatibilidad con IDataStorage
    def save_data(self, table_name: str, data: pd.DataFrame) -> bool:
        """Guarda datos en el almacenamiento (implementación de IDataStorage)"""
        try:
            # Extraer símbolo y timeframe del nombre de tabla
            parts = table_name.split('_')
            if len(parts) >= 3:
                symbol = parts[0] + '/' + parts[1]  # Reconstruir símbolo
                timeframe = parts[2]
            else:
                symbol = "UNKNOWN"
                timeframe = "1h"
            
            # Crear IOHLCVData mock para usar save_ohlcv_data
            from ..core.data_adapters import OHLCVData
            ohlcv_data = OHLCVData(data)
            
            return self.save_ohlcv_data(symbol, timeframe, ohlcv_data)
        except Exception as e:
            self.logger.error(f"Error en save_data: {e}")
            return False
    
    def query_data(self, table_name: str, start_ts: Optional[int] = None, 
                   end_ts: Optional[int] = None) -> pd.DataFrame:
        """Consulta datos del almacenamiento (implementación de IDataStorage)"""
        try:
            # Extraer símbolo y timeframe del nombre de tabla
            parts = table_name.split('_')
            if len(parts) >= 3:
                symbol = parts[0] + '/' + parts[1]  # Reconstruir símbolo
                timeframe = parts[2]
            else:
                symbol = "UNKNOWN"
                timeframe = "1h"
            
            # Convertir timestamps a fechas
            start_date = None
            end_date = None
            
            if start_ts:
                start_date = pd.to_datetime(start_ts, unit='s').strftime('%Y-%m-%d')
            if end_ts:
                end_date = pd.to_datetime(end_ts, unit='s').strftime('%Y-%m-%d')
            
            result = self.load_ohlcv_data(symbol, timeframe, start_date, end_date)
            return result if result is not None else pd.DataFrame()
            
        except Exception as e:
            self.logger.error(f"Error en query_data: {e}")
            return pd.DataFrame()
    
    def table_exists(self, table_name: str) -> bool:
        """Verifica si una tabla existe (implementación de IDataStorage)"""
        try:
            # Extraer símbolo y timeframe del nombre de tabla
            parts = table_name.split('_')
            if len(parts) >= 3:
                symbol = parts[0] + '/' + parts[1]  # Reconstruir símbolo
                timeframe = parts[2]
                return self.data_exists(symbol, timeframe)
            else:
                return False
        except Exception as e:
            self.logger.error(f"Error en table_exists: {e}")
            return False
    
    def close(self):
        """Cierra conexiones y limpia recursos"""
        if self._connection:
            self._connection.close()
            self._connection = None
        
        self.logger.info("Storage cerrado correctamente")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del storage"""
        stats = self.storage_stats.copy()
        
        # Agregar información de espacio en disco
        if self.sqlite_path.exists():
            stats['sqlite_size_mb'] = self.sqlite_path.stat().st_size / (1024 * 1024)
        
        if self.csv_path.exists():
            csv_size = sum(f.stat().st_size for f in self.csv_path.rglob('*.csv'))
            stats['csv_size_mb'] = csv_size / (1024 * 1024)
        
        return stats

    # === IMPLEMENTACIÓN DE INTERFAZ IDataStorage ===

    def save_data(self, symbol: str, data: Union[pd.DataFrame, IOHLCVData], timeframe: str) -> bool:
        """Implementación de IDataStorage.save_data"""
        # Si es un DataFrame, lo convertimos a un objeto compatible con IOHLCVData
        if isinstance(data, pd.DataFrame):
            # Crear un wrapper simple para el DataFrame
            class DataFrameWrapper:
                def __init__(self, df: pd.DataFrame):
                    self._df = df
                def get_dataframe(self) -> pd.DataFrame:
                    return self._df
                def get_timeframe(self) -> str:
                    return timeframe
            
            data = DataFrameWrapper(data)
        
        return self.save_ohlcv_data(symbol, timeframe, data)

    def load_data(self, symbol: str, timeframe: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Implementación de IDataStorage.load_data"""
        return self.load_ohlcv_data(symbol, timeframe, start_date, end_date)

    def save_to_sqlite(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Alias para guardar directamente en SQLite"""
        from .interfaces import OHLCVData
        data = OHLCVData(df, timeframe)
        return self.save_ohlcv_data(symbol, timeframe, data)
