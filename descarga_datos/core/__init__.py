"""
Módulo core con componentes optimizados del sistema de trading.
"""

# Interfaces principales
from .interfaces import (
    IStrategy,
    IDataStorage,
    IBacktester,
    IDataValidator,
    IOHLCVData,
    IDataDownloader,
    IDataAdapter,
    ICacheManager,
    TradingSignal,
    TradeResult,
    SystemConfig,
    ExchangeConfig,
    StorageConfig
)

# Componentes principales
from .base_data_handler import BaseDataHandler, DataValidationResult
from .cache_manager import InMemoryCache
from .data_adapters import OHLCVData, AdapterFactory
from .data_validator import DataValidator, ValidationResult
from .downloader import AdvancedDataDownloader
from .mt5_downloader import MT5Downloader
from .unified_storage import UnifiedDataStorage
from .config_manager import ConfigManager, get_config_manager, load_system_config
from .base_strategy import BaseStrategy, Signal, Position, SignalType

__all__ = [
    # Interfaces
    'IStrategy',
    'IDataStorage',
    'IBacktester',
    'IDataValidator',
    'IOHLCVData',
    'IDataDownloader',
    'IDataAdapter',
    'ICacheManager',
    'TradingSignal',
    'TradeResult',
    'SystemConfig',
    'ExchangeConfig',
    'StorageConfig',

    # Componentes
    'BaseDataHandler',
    'DataValidationResult',
    'InMemoryCache',
    'OHLCVData',
    'AdapterFactory',
    'DataValidator',
    'ValidationResult',
    'AdvancedDataDownloader',
    'MT5Downloader',
    'UnifiedDataStorage',
    'ConfigManager',
    'get_config_manager',
    'load_system_config',
    'BaseStrategy',
    'Signal',
    'Position',
    'SignalType'
]