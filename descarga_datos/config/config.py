import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any

@dataclass
class StorageConfig:
    path: str = "data"
    csv: Dict[str, bool] = field(default_factory=lambda: {'enabled': True})
    sqlite: Dict[str, bool] = field(default_factory=lambda: {'enabled': True})

@dataclass
class NormalizationConfig:
    enabled: bool = True
    method: str = "minmax"
    feature_range: tuple = (0, 1)
    with_mean: bool = True
    with_std: bool = True
    quantile_range: tuple = (25.0, 75.0)

@dataclass
class IndicatorConfig:
    volatility: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'period': 14,
        'method': 'standard_deviation'
    })
    heiken_ashi: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'trend_period': 3,
        'size_comparison_threshold': 1.2
    })
    atr: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'period': 14
    })
    adx: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'period': 14,
        'threshold': 25
    })
    ema: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'periods': [10, 20, 200]
    })
    parabolic_sar: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'acceleration': 0.02,
        'maximum': 0.2
    })
    normalize_output: bool = True

@dataclass
class MT5Config:
    enabled: bool = False
    terminal_path: str = ""
    server: str = ""
    login: int = 0
    password: str = ""
    timeout: int = 60000
    default_symbol_list: List[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    default_timeframe: str = "1h"
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1h", "4h", "1d"])
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    use_real_volume: bool = True
    max_bars: int = 10000

@dataclass
class Config:
    active_exchange: str = "bybit"
    exchanges: Dict[str, Dict[str, str]] = None
    default_symbols: List[str] = None
    data_types: List[str] = None
    max_retries: int = 3
    retry_delay: int = 5
    log_level: str = "INFO"
    log_file: str = "data_downloader.log"
    storage: StorageConfig = field(default_factory=StorageConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    timeframe: str = "1d"
    # MT5 config
    use_mt5: bool = False
    mt5: MT5Config = field(default_factory=MT5Config)

    def __post_init__(self):
        if self.exchanges is None:
            self.exchanges = {}
        if self.default_symbols is None:
            self.default_symbols = ["BTC/USDT", "ETH/USDT"]
        if self.data_types is None:
            self.data_types = ["ohlcv"]
    
    def get_symbol_config(self, symbol: str) -> Dict[str, Any]:
        """Obtiene configuración específica para un símbolo"""
        # Configuración básica por defecto para cualquier símbolo
        return {
            # Porcentaje máximo del portfolio (ej: 10 = 10%)
            'max_position_size': 10.0,
            'min_position_size': 10.0,
            'leverage': 1.0,
            'commission': 0.001,
            'slippage': 0.0001
        }
