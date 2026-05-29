#!/usr/bin/env python3
"""
Cargador de configuración centralizada para Bot Trader Copilot.
Lee la configuración desde config.yaml y la estructura en objetos Python.
"""
import yaml
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ExchangeConfig:
    enabled: bool = False
    api_key: str = ""
    api_secret: str = ""
    password: str = ""
    sandbox: bool = False
    timeout: int = 30000

@dataclass
class MT5Config:
    enabled: bool = False
    terminal_path: str = ""
    server: str = ""
    login: int = 0
    password: str = ""
    timeout: int = 60000

@dataclass
class BacktestingConfig:
    symbols: List[str] = field(default_factory=list)
    timeframe: str = "1h"
    start_date: str = "2024-01-01"
    end_date: str = "2024-06-01"
    initial_capital: float = 10000.0
    commission: float = 0.1
    slippage: float = 0.05
    strategies: Dict[str, bool] = field(default_factory=dict)

@dataclass
class IndicatorsConfig:
    volatility: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'period': 14})
    heiken_ashi: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'trend_period': 3, 'size_comparison_threshold': 1.2})
    atr: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'period': 14})
    ema: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'periods': [10, 20, 200]})
    parabolic_sar: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'acceleration': 0.02, 'maximum': 0.2})
    adx: Dict[str, Any] = field(default_factory=lambda: {'enabled': True, 'period': 14, 'threshold': 25})

@dataclass
class StorageConfig:
    path: str = "data"
    csv_enabled: bool = True
    sqlite_enabled: bool = True
    cache_enabled: bool = True

@dataclass
class RiskConfig:
    risk_percent: float = 2.0
    tp_atr_multiplier: float = 2.0
    sl_atr_multiplier: float = 1.5
    max_drawdown_limit: float = 20.0

@dataclass
class DataConfig:
    use_mt5_for_stocks: bool = False
    use_ccxt_for_crypto: bool = True
    max_retries: int = 3
    retry_delay: int = 5
    limit_per_request: int = 1000
    validate_data: bool = True

@dataclass
class ReportsConfig:
    save_individual_results: bool = True
    save_equity_curves: bool = True
    save_trade_details: bool = True
    generate_comparison: bool = True
    output_directory: str = "backtest_results"

@dataclass
class SystemConfig:
    name: str = "Bot Trader Copilot"
    version: str = "1.0"
    log_level: str = "INFO"
    log_file: str = "logs/bot_trader.log"
    auto_launch_dashboard: bool = True

@dataclass
class Config:
    system: SystemConfig = field(default_factory=SystemConfig)
    active_exchange: str = "bybit"  # Exchange activo por defecto
    exchanges: Dict[str, ExchangeConfig] = field(default_factory=dict)
    mt5: MT5Config = field(default_factory=MT5Config)
    backtesting: BacktestingConfig = field(default_factory=BacktestingConfig)
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    data: DataConfig = field(default_factory=DataConfig)
    reports: ReportsConfig = field(default_factory=ReportsConfig)

def load_config_from_yaml(config_path: Optional[str] = None) -> Config:
    """
    Carga la configuración desde archivo YAML.

    Args:
        config_path: Ruta al archivo de configuración. Si es None, busca en config/config.yaml

    Returns:
        Config: Objeto de configuración cargado
    """
    if config_path is None:
        # Buscar en el directorio del script
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            yaml_data = yaml.safe_load(file)

        if yaml_data is None:
            raise ValueError("El archivo de configuración está vacío")

        # Crear configuración base
        config = Config()

        # Cargar configuración del sistema
        if 'system' in yaml_data:
            system_data = yaml_data['system']
            config.system = SystemConfig(**system_data)

        # Cargar exchange activo
        if 'active_exchange' in yaml_data:
            config.active_exchange = yaml_data['active_exchange']

        # Cargar configuración de exchanges
        if 'exchanges' in yaml_data:
            exchanges_data = yaml_data['exchanges']
            config.exchanges = {}
            for exchange_name, exchange_data in exchanges_data.items():
                config.exchanges[exchange_name] = ExchangeConfig(**exchange_data)

        # Cargar configuración MT5
        if 'mt5' in yaml_data:
            mt5_data = yaml_data['mt5']
            config.mt5 = MT5Config(**mt5_data)

        # Cargar configuración de backtesting
        if 'backtesting' in yaml_data:
            bt_data = yaml_data['backtesting']
            config.backtesting = BacktestingConfig(**bt_data)

        # Cargar configuración de indicadores
        if 'indicators' in yaml_data:
            ind_data = yaml_data['indicators']
            config.indicators = IndicatorsConfig(**ind_data)

        # Cargar configuración de almacenamiento
        if 'storage' in yaml_data:
            storage_data = yaml_data['storage']
            config.storage = StorageConfig(**storage_data)

        # Cargar configuración de riesgo
        if 'risk' in yaml_data:
            risk_data = yaml_data['risk']
            config.risk = RiskConfig(**risk_data)

        # Cargar configuración de datos
        if 'data' in yaml_data:
            data_config = yaml_data['data']
            config.data = DataConfig(**data_config)

        # Cargar configuración de reportes
        if 'reports' in yaml_data:
            reports_data = yaml_data['reports']
            config.reports = ReportsConfig(**reports_data)

        return config

    except Exception as e:
        raise RuntimeError(f"Error cargando configuración: {e}")

def save_config_to_yaml(config: Config, config_path: Optional[str] = None) -> None:
    """
    Guarda la configuración en archivo YAML.

    Args:
        config: Objeto de configuración a guardar
        config_path: Ruta donde guardar el archivo
    """
    if config_path is None:
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.yaml"

    # Convertir a diccionario para YAML
    config_dict = {
        'system': {
            'name': config.system.name,
            'version': config.system.version,
            'log_level': config.system.log_level,
            'log_file': config.system.log_file
        },
        'exchanges': {
            name: {
                'enabled': exchange.enabled,
                'api_key': exchange.api_key,
                'api_secret': exchange.api_secret,
                'sandbox': exchange.sandbox,
                'timeout': exchange.timeout
            }
            for name, exchange in config.exchanges.items()
        },
        'mt5': {
            'enabled': config.mt5.enabled,
            'terminal_path': config.mt5.terminal_path,
            'server': config.mt5.server,
            'login': config.mt5.login,
            'password': config.mt5.password,
            'timeout': config.mt5.timeout
        },
        'backtesting': {
            'symbols': config.backtesting.symbols,
            'timeframe': config.backtesting.timeframe,
            'start_date': config.backtesting.start_date,
            'end_date': config.backtesting.end_date,
            'initial_capital': config.backtesting.initial_capital,
            'commission': config.backtesting.commission,
            'slippage': config.backtesting.slippage,
            'strategies': config.backtesting.strategies
        },
        'indicators': {
            'atr': config.indicators.atr,
            'ema': config.indicators.ema,
            'parabolic_sar': config.indicators.parabolic_sar,
            'adx': config.indicators.adx
        },
        'storage': {
            'path': config.storage.path,
            'csv_enabled': config.storage.csv_enabled,
            'sqlite_enabled': config.storage.sqlite_enabled,
            'cache_enabled': config.storage.cache_enabled
        },
        'risk': {
            'risk_percent': config.risk.risk_percent,
            'tp_atr_multiplier': config.risk.tp_atr_multiplier,
            'sl_atr_multiplier': config.risk.sl_atr_multiplier,
            'max_drawdown_limit': config.risk.max_drawdown_limit
        },
        'data': {
            'use_mt5_for_stocks': config.data.use_mt5_for_stocks,
            'use_ccxt_for_crypto': config.data.use_ccxt_for_crypto,
            'max_retries': config.data.max_retries,
            'retry_delay': config.data.retry_delay,
            'limit_per_request': config.data.limit_per_request,
            'validate_data': config.data.validate_data
        },
        'reports': {
            'save_individual_results': config.reports.save_individual_results,
            'save_equity_curves': config.reports.save_equity_curves,
            'save_trade_details': config.reports.save_trade_details,
            'generate_comparison': config.reports.generate_comparison,
            'output_directory': config.reports.output_directory
        }
    }

    # Crear directorio si no existe
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Guardar en YAML
    with open(config_path, 'w', encoding='utf-8') as file:
        yaml.dump(config_dict, file, default_flow_style=False, allow_unicode=True)

def get_active_exchanges(config: Config) -> List[str]:
    """Retorna lista de exchanges activos"""
    return [name for name, exchange in config.exchanges.items() if exchange.enabled]

def get_enabled_strategies(config: Config) -> List[str]:
    """Retorna lista de estrategias activadas"""
    return [name for name, enabled in config.backtesting.strategies.items() if enabled]

def print_config_summary(config: Config) -> None:
    """Imprime resumen de la configuración actual"""
    print("🤖 CONFIGURACIÓN DE BOT TRADER COPILOT")
    print("=" * 50)
    print(f"Sistema: {config.system.name} v{config.system.version}")
    print(f"Log level: {config.system.log_level}")
    print()

    print("📊 BACKTESTING:")
    print(f"  Símbolos: {len(config.backtesting.symbols)}")
    print(f"  Temporalidad: {config.backtesting.timeframe}")
    print(f"  Período: {config.backtesting.start_date} a {config.backtesting.end_date}")
    print(f"  Capital inicial: ${config.backtesting.initial_capital}")
    print()

    print("🔄 EXCHANGES ACTIVOS:")
    active_exchanges = get_active_exchanges(config)
    for exchange in active_exchanges:
        print(f"  • {exchange}")
    print()

    print("🎯 ESTRATEGIAS ACTIVAS:")
    enabled_strategies = get_enabled_strategies(config)
    for strategy in enabled_strategies:
        print(f"  • {strategy}")
    print()

    print("💰 CONFIGURACIÓN DE RIESGO:")
    print(f"  • Riesgo por operación: {config.risk.risk_percent}%")
    print(f"  • Take Profit: {config.risk.tp_atr_multiplier}x ATR")
    print(f"  • Stop Loss: {config.risk.sl_atr_multiplier}x ATR")
    print("=" * 50)

if __name__ == "__main__":
    # Cargar y mostrar configuración
    config = load_config_from_yaml()
    print_config_summary(config)
