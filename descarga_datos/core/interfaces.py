#!/usr/bin/env python3
"""
Interfaces del Sistema Core - Bot Trader Copilot
===============================================

Define las interfaces principales del sistema para mantener consistencia
y facilitar el desarrollo modular.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol, Union
from datetime import datetime
import pandas as pd

# === INTERFACES DE DATOS ===

class IOHLCVData(Protocol):
    """Protocolo para datos OHLCV"""

    def get_dataframe(self) -> pd.DataFrame:
        """Retorna los datos como DataFrame"""
        ...

    def get_timeframe(self) -> str:
        """Retorna el timeframe de los datos"""
        ...

# === INTERFACES DE COMPONENTES CORE ===

class IDataStorage(ABC):
    """Interfaz para sistemas de almacenamiento de datos"""

    @abstractmethod
    def save_data(self, symbol: str, data: pd.DataFrame, timeframe: str) -> bool:
        """Guarda datos en el almacenamiento"""
        pass

    @abstractmethod
    def load_data(self, symbol: str, timeframe: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Carga datos del almacenamiento"""
        pass

    @abstractmethod
    def data_exists(self, symbol: str, timeframe: str) -> bool:
        """Verifica si los datos existen"""
        pass

class IDataValidator(ABC):
    """Interfaz para validadores de datos"""

    @abstractmethod
    def validate_ohlcv_data(self, data: pd.DataFrame) -> Any:
        """Valida datos OHLCV"""
        pass

class IDataAdapter(ABC):
    """Interfaz para adaptadores de datos"""

    @abstractmethod
    def adapt_data(self, raw_data: Any) -> IOHLCVData:
        """Adapta datos crudos al formato estándar"""
        pass

class ICacheManager(ABC):
    """Interfaz para gestores de caché"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Guarda un valor en el caché"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Elimina un valor del caché"""
        pass

class IDataDownloader(ABC):
    """Interfaz para descargadores de datos"""

    @abstractmethod
    async def download_symbol_data(self, symbol: str, timeframe: str, start_date: str, end_date: str) -> IOHLCVData:
        """Descarga datos de un símbolo"""
        pass

    @abstractmethod
    async def download_multiple_symbols(self, symbols: List[str], timeframe: str, start_date: str, end_date: str) -> Dict[str, IOHLCVData]:
        """Descarga datos de múltiples símbolos"""
        pass

# === INTERFACES DE TRADING ===

class IStrategy(ABC):
    """Interfaz para estrategias de trading"""

    @abstractmethod
    def generate_signals(self, data: IOHLCVData) -> List[Any]:
        """Genera señales de trading"""
        pass

    @abstractmethod
    def calculate_position_size(self, signal: Any, capital: float) -> float:
        """Calcula el tamaño de posición"""
        pass

class IBacktester(ABC):
    """Interfaz para backtesters"""

    @abstractmethod
    def run_backtest(self, strategy: IStrategy, data: IOHLCVData, initial_capital: float) -> Any:
        """Ejecuta un backtest"""
        pass

# === TIPOS DE DATOS ===

class TradingSignal:
    """Señal de trading estandarizada"""
    def __init__(self, symbol: str, signal_type: str, price: float, timestamp: datetime,
                 confidence: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.signal_type = signal_type  # 'BUY', 'SELL', 'HOLD'
        self.price = price
        self.timestamp = timestamp
        self.confidence = confidence
        self.metadata = metadata or {}

class TradeResult:
    """Resultado de un trade"""
    def __init__(self, symbol: str, entry_price: float, exit_price: float,
                 entry_time: datetime, exit_time: datetime, pnl: float,
                 pnl_percentage: float, quantity: float):
        self.symbol = symbol
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.pnl = pnl
        self.pnl_percentage = pnl_percentage
        self.quantity = quantity

# === CONFIGURACIONES ===

class SystemConfig:
    """Configuración general del sistema"""
    def __init__(self):
        self.storage_path = "data"
        self.cache_size_mb = 100
        self.max_retries = 3
        self.retry_delay = 5
        self.log_level = "INFO"

class ExchangeConfig:
    """Configuración de exchange"""
    def __init__(self, name: str, api_key: str = "", api_secret: str = "",
                 sandbox: bool = True, timeout: int = 30000, rate_limit: int = 10):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.enabled = True

class StorageConfig:
    """Configuración de almacenamiento"""
    def __init__(self, sqlite_path: str = "data/market_data.db", csv_path: str = "data/csv", enable_sqlite: bool = True, enable_csv: bool = True):
        self.sqlite_path = sqlite_path
        self.csv_path = csv_path
        self.enable_sqlite = enable_sqlite
        self.enable_csv = enable_csv

# === FUNCIONES DE UTILIDAD ===

def create_exchange_config(name: str, **kwargs) -> ExchangeConfig:
    """Crea una configuración de exchange"""
    return ExchangeConfig(name, **kwargs)

def create_storage_config(sqlite_path: str = "data/market_data.db", csv_path: str = "data/csv", enable_sqlite: bool = True, enable_csv: bool = True) -> StorageConfig:
    """Crea una configuración de almacenamiento"""
    return StorageConfig(sqlite_path, csv_path, enable_sqlite, enable_csv)

# === IMPLEMENTACIONES CONCRETAS ===

class OHLCVData:
    """Implementación concreta de IOHLCVData"""
    
    def __init__(self, dataframe: pd.DataFrame, timeframe: str = "1h"):
        self._dataframe = dataframe
        self._timeframe = timeframe
    
    def get_dataframe(self) -> pd.DataFrame:
        return self._dataframe
    
    def get_timeframe(self) -> str:
        return self._timeframe
