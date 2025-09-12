#!/usr/bin/env python3
"""
Config Manager - Gestor de Configuración Centralizado
===================================================

Maneja todas las configuraciones del sistema de forma centralizada
y proporciona una interfaz unificada para acceder a ellas.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging
from dataclasses import dataclass, asdict

from .interfaces import SystemConfig, ExchangeConfig, StorageConfig

@dataclass
class RiskConfig:
    """Configuración de gestión de riesgo"""
    max_drawdown: float = 0.15  # 15%
    max_correlation: float = 0.7
    kelly_fraction: float = 0.1
    max_positions: int = 10
    position_size_percent: float = 0.02  # 2% por posición

@dataclass
class StrategyConfig:
    """Configuración de estrategias"""
    enabled_strategies: list = None
    min_signal_strength: float = 0.6
    max_hold_time_days: int = 30
    profit_target_percent: float = 0.05
    stop_loss_percent: float = 0.02

    def __post_init__(self):
        if self.enabled_strategies is None:
            self.enabled_strategies = ["ut_bot_psar", "optimized_strategy"]

@dataclass
class BacktestingConfig:
    """Configuración de backtesting"""
    symbols: list = None
    timeframe: str = "1h"
    start_date: str = "2024-01-01"
    end_date: str = "2024-06-01"
    initial_capital: float = 10000.0
    commission: float = 0.1
    slippage: float = 0.05
    max_symbols: int = 0

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTC/USDT", "ETH/USDT", "TSLA.US", "AAPL.US"]

@dataclass
class IndicatorsConfig:
    """Configuración de indicadores técnicos"""
    volatility: dict = None
    heiken_ashi: dict = None
    atr: dict = None
    adx: dict = None
    ema: dict = None
    parabolic_sar: dict = None
    normalize_output: bool = True

    def __post_init__(self):
        if self.volatility is None:
            self.volatility = {'enabled': True, 'period': 14, 'method': 'standard_deviation'}
        if self.heiken_ashi is None:
            self.heiken_ashi = {'enabled': True, 'trend_period': 3, 'size_comparison_threshold': 1.2}
        if self.atr is None:
            self.atr = {'enabled': True, 'period': 14}
        if self.adx is None:
            self.adx = {'enabled': True, 'period': 14, 'threshold': 25}
        if self.ema is None:
            self.ema = {'enabled': True, 'periods': [10, 20, 200]}
        if self.parabolic_sar is None:
            self.parabolic_sar = {'enabled': True, 'acceleration': 0.02, 'maximum': 0.2}

@dataclass
class MT5Config:
    """Configuración de MT5"""
    enabled: bool = True
    server: str = "MetaQuotes-Demo"
    login: int = 12345678
    password: str = "password"
    path: str = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    symbols: list = None
    timeframes: list = None
    max_bars: int = 10000
    timeout: int = 60000

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
        if self.timeframes is None:
            self.timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]

@dataclass
class ExchangeConfig:
    """Configuración de exchanges"""
    name: str = "bybit"
    api_key: str = ""
    api_secret: str = ""
    sandbox: bool = True
    rate_limit: int = 10
    timeout: int = 30000
    retry_count: int = 3
    retry_delay: int = 5

@dataclass
class SystemConfig:
    """Configuración del sistema"""
    log_level: str = "INFO"
    log_file: str = "logs/trading_bot.log"
    data_cache_dir: str = "data/cache"
    models_dir: str = "models"
    reports_dir: str = "reports"
    max_workers: int = 4
    memory_limit_gb: float = 8.0
    enable_monitoring: bool = True
    enable_alerts: bool = True

@dataclass
class NormalizationConfig:
    """Configuración de normalización"""
    enabled: bool = True
    method: str = "minmax"
    feature_range: tuple = (0, 1)
    with_mean: bool = True
    with_std: bool = True
    quantile_range: tuple = (25.0, 75.0)

@dataclass
class UnifiedConfig:
    """Configuración unificada del sistema"""
    system: SystemConfig = None
    exchanges: dict = None
    mt5: MT5Config = None
    backtesting: BacktestingConfig = None
    strategies: StrategyConfig = None
    indicators: IndicatorsConfig = None
    risk_management: RiskConfig = None
    storage: StorageConfig = None
    normalization: NormalizationConfig = None

    def __post_init__(self):
        if self.system is None:
            self.system = SystemConfig()
        if self.exchanges is None:
            self.exchanges = {
                "bybit": ExchangeConfig(name="bybit"),
                "binance": ExchangeConfig(name="binance"),
                "kraken": ExchangeConfig(name="kraken")
            }
        if self.mt5 is None:
            self.mt5 = MT5Config()
        if self.backtesting is None:
            self.backtesting = BacktestingConfig()
        if self.strategies is None:
            self.strategies = StrategyConfig()
        if self.indicators is None:
            self.indicators = IndicatorsConfig()
        if self.risk_management is None:
            self.risk_management = RiskConfig()
        if self.storage is None:
            self.storage = StorageConfig()
        if self.normalization is None:
            self.normalization = NormalizationConfig()

class ConfigManager:
    """Gestor centralizado de configuraciones"""

    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path) if config_path else self._find_config_path()
        self._config_cache: Optional[Dict[str, Any]] = None
        self._last_load_time: Optional[float] = None

    def _find_config_path(self) -> Path:
        """Encuentra la ruta del archivo de configuración"""
        possible_paths = [
            Path("config/config.yaml"),
            Path("config/config.json"),
            Path("../config/config.yaml"),
            Path("../config/config.json"),
            Path("../../config/config.yaml"),
            Path("../../config/config.json"),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Si no existe, crear configuración por defecto
        return Path("config/config.json")

    def load_config(self) -> SystemConfig:
        """Carga la configuración desde archivo o crea configuración por defecto"""
        try:
            if self.config_path.exists():
                return self._load_from_file()
            else:
                self.logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
                return self._create_default_config()
        except Exception as e:
            self.logger.error(f"Error cargando configuración: {e}")
            return self._create_default_config()

    def _load_from_file(self) -> SystemConfig:
        """Carga configuración desde archivo"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix == '.json':
                    data = json.load(f)
                else:
                    # Para archivos YAML, usar configuración básica por ahora
                    data = {}

            return self._parse_config_data(data)
        except Exception as e:
            self.logger.error(f"Error leyendo archivo de configuración: {e}")
            return self._create_default_config()

    def _parse_config_data(self, data: Dict[str, Any]) -> SystemConfig:
        """Parsea los datos de configuración"""
        config = SystemConfig()

        # Configuración de sistema
        if 'system' in data:
            sys_data = data['system']
            config.storage_path = sys_data.get('storage_path', 'data')
            config.cache_size_mb = sys_data.get('cache_size_mb', 100)
            config.max_retries = sys_data.get('max_retries', 3)
            config.retry_delay = sys_data.get('retry_delay', 5)
            config.log_level = sys_data.get('log_level', 'INFO')

        # Exchanges
        if 'exchanges' in data:
            config.exchanges = {}
            for name, exch_data in data['exchanges'].items():
                config.exchanges[name] = ExchangeConfig(
                    name=name,
                    api_key=exch_data.get('api_key', ''),
                    api_secret=exch_data.get('api_secret', ''),
                    sandbox=exch_data.get('sandbox', True),
                    timeout=exch_data.get('timeout', 30000),
                    rate_limit=exch_data.get('rate_limit', 10)
                )

        # MT5
        if 'mt5' in data:
            config.mt5 = MT5Config(**data['mt5'])

        # Riesgo
        if 'risk' in data:
            config.risk = RiskConfig(**data['risk'])

        # Estrategias
        if 'strategy' in data:
            config.strategy = StrategyConfig(**data['strategy'])

        return config

    def _create_default_config(self) -> SystemConfig:
        """Crea una configuración por defecto"""
        config = SystemConfig()

        # Configuración por defecto de exchanges
        config.exchanges = {
            'bybit': ExchangeConfig(
                name='bybit',
                api_key='',
                api_secret='',
                sandbox=True,
                timeout=30000,
                rate_limit=10
            ),
            'binance': ExchangeConfig(
                name='binance',
                api_key='',
                api_secret='',
                sandbox=True,
                timeout=30000,
                rate_limit=10
            )
        }

        # Configuración MT5 por defecto
        config.mt5 = MT5Config()

        # Configuración de riesgo por defecto
        config.risk = RiskConfig()

        # Configuración de estrategias por defecto
        config.strategy = StrategyConfig()

        return config

    def save_config(self, config: SystemConfig, path: Optional[str] = None) -> bool:
        """Guarda la configuración en archivo"""
        try:
            save_path = Path(path) if path else self.config_path
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Convertir a diccionario
            config_dict = {
                'system': {
                    'storage_path': config.storage_path,
                    'cache_size_mb': config.cache_size_mb,
                    'max_retries': config.max_retries,
                    'retry_delay': config.retry_delay,
                    'log_level': config.log_level
                },
                'exchanges': {
                    name: {
                        'api_key': exch.api_key,
                        'api_secret': exch.api_secret,
                        'sandbox': exch.sandbox,
                        'timeout': exch.timeout,
                        'rate_limit': exch.rate_limit
                    } for name, exch in config.exchanges.items()
                },
                'mt5': asdict(config.mt5) if hasattr(config, 'mt5') else asdict(MT5Config()),
                'risk': asdict(config.risk) if hasattr(config, 'risk') else asdict(RiskConfig()),
                'strategy': asdict(config.strategy) if hasattr(config, 'strategy') else asdict(StrategyConfig())
            }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Configuración guardada en: {save_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error guardando configuración: {e}")
            return False

    def get_exchange_config(self, name: str) -> Optional[ExchangeConfig]:
        """Obtiene la configuración de un exchange específico"""
        config = self.load_config()
        return config.exchanges.get(name)

    def get_mt5_config(self) -> MT5Config:
        """Obtiene la configuración de MT5"""
        config = self.load_config()
        return config.mt5 if hasattr(config, 'mt5') else MT5Config()

    def get_risk_config(self) -> RiskConfig:
        """Obtiene la configuración de riesgo"""
        config = self.load_config()
        return config.risk if hasattr(config, 'risk') else RiskConfig()

    def get_strategy_config(self) -> StrategyConfig:
        """Obtiene la configuración de estrategias"""
        config = self.load_config()
        return config.strategy if hasattr(config, 'strategy') else StrategyConfig()

# === FUNCIONES GLOBALES ===

_config_manager_instance: Optional[ConfigManager] = None

def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Obtiene la instancia global del gestor de configuración"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_path)
    return _config_manager_instance

def load_system_config() -> SystemConfig:
    """Carga la configuración del sistema"""
    manager = get_config_manager()
    return manager.load_config()

def save_system_config(config: SystemConfig, path: Optional[str] = None) -> bool:
    """Guarda la configuración del sistema"""
    manager = get_config_manager()
    return manager.save_config(config, path)
