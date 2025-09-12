# 🤖 Trading Bot Copilot - Sistema Avanzado de Trading Automatizado
### ✅ **Sistema Unificado de Almacenamiento**
- **SQLite + CSV híbrido** - Optimización automática
- **Validación integrada** - Datos consistentes y confiables
- **Compresión inteligente** - Eficiencia máxima
- **Compatibilidad total** - Código existente funciona sin cambios
- **Interfaz unificada** - API consistente y simple

## 🆕 **Mejoras Recientes v1.0**

### 🚀 **Integración Completa del Sistema de Almacenamiento**
- ✅ **Sistema unificado operativo** - `UnifiedDataStorage` con interfaz `IDataStorage`
- ✅ **Compatibilidad hacia atrás** - Todas las importaciones existentes funcionan
- ✅ **Módulo de compatibilidad** - `utils/storage.py` para código legacy
- ✅ **Archivos duplicados eliminados** - Proyecto completamente limpio
- ✅ **Validación integrada** - Timestamps y datos consistentes
- ✅ **Optimización automática** - SQLite + CSV según necesidades

### 📊 **Estado del Sistema**
```bash
✅ Sistema unificado de configuración
✅ Integración multi-exchange (Bybit, Binance, MT5)
✅ Estrategias avanzadas implementadas
✅ Backtesting robusto con métricas avanzadas
✅ Gestión de riesgo inteligente
✅ Indicadores técnicos completos
✅ Almacenamiento unificado operativo
✅ Compatibilidad total con código existente
```

## 🏗️ Arquitectura del Sistemahon](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.1-orange.svg)]()

> Sistema de trading automatizado con IA que integra múltiples exchanges, estrategias avanzadas y gestión de riesgo inteligente.

## 📋 Tabla de Contenidos

- [🚀 Características Principales](#-características-principales)
- [� Mejoras Recientes v1.0](#-mejoras-recientes-v10)
- [�🏗️ Arquitectura del Sistema](#️-arquitectura-del-sistema)
- [📦 Estructura del Proyecto](#-estructura-del-proyecto)
- [⚙️ Configuración](#️-configuración)
- [🔧 Instalación](#-instalación)
- [📊 Uso del Sistema](#-uso-del-sistema)
- [🎯 Estrategias Implementadas](#-estrategias-implementadas)
- [📈 Sistema de Backtesting](#-sistema-de-backtesting)
- [🛡️ Gestión de Riesgo](#️-gestión-de-riesgo)
- [📊 Dashboard y Monitoreo](#-dashboard-y-monitoreo)
- [🔍 Indicadores Técnicos](#-indicadores-técnicos)
- [💾 Almacenamiento de Datos](#-almacenamiento-de-datos)
- [🧪 Testing](#-testing)
- [📚 API Reference](#-api-reference)
- [🔧 Desarrollo](#-desarrollo)
- [📝 Changelog](#-changelog)
- [🤝 Contribución](#-contribución)
- [📄 Licencia](#-licencia)

## 🚀 Características Principales

### ✅ **Sistema Unificado de Configuración**
- Configuración centralizada y modular
- Compatibilidad hacia atrás con configuraciones existentes
- Soporte para múltiples formatos (YAML, JSON, Python dataclasses)
- Validación automática de configuraciones

### ✅ **Integración Multi-Exchange**
- **Bybit** - Exchange principal con API avanzada
- **Binance** - Exchange global con alto volumen
- **Kraken** - Exchange especializado en criptomonedas
- **MT5** - Plataforma de trading profesional

### ✅ **Estrategias Avanzadas**
- **UT Bot PSAR** - Estrategia basada en Parabolic SAR
- **UT Bot PSAR Conservadora** - Versión conservadora
- **UT Bot PSAR Optimizada** - Versión optimizada
- **Estrategia Optimizada** - Estrategia adaptativa

### ✅ **Sistema de Backtesting Robusto**
- Backtesting histórico con datos reales
- Métricas avanzadas (Sharpe, Sortino, Calmar, etc.)
- Optimización de parámetros
- Análisis de drawdown y riesgo

### ✅ **Gestión de Riesgo Inteligente**
- Control de drawdown máximo
- Gestión de posiciones por tamaño y correlación
- Stop-loss y take-profit dinámicos
- Kelly Criterion para sizing óptimo

### ✅ **Indicadores Técnicos Avanzados**
- **Volatility** - Medidas de volatilidad
- **Heikin-Ashi** - Velas suavizadas
- **ATR** - Average True Range
- **ADX** - Average Directional Index
- **EMA** - Exponential Moving Average
- **Parabolic SAR** - Sistema de seguimiento de tendencias

### ✅ **Sistema Unificado de Almacenamiento**
- **SQLite + CSV híbrido** - Optimización automática
- **Validación integrada** - Datos consistentes y confiables
- **Compresión inteligente** - Eficiencia máxima
- **Compatibilidad total** - Código existente funciona sin cambios
- **Interfaz unificada** - API consistente y simple

## 🏗️ Arquitectura del Sistema

```
📁 Trading Bot Copilot v1.0
├── 🎯 core/                    # Núcleo del sistema
│   ├── config_manager.py       # Gestor de configuración unificado
│   ├── base_data_handler.py    # Manejador base de datos
│   ├── cache_manager.py        # Sistema de caché
│   ├── data_adapters.py        # Adaptadores de datos
│   └── unified_storage.py      # Almacenamiento unificado
├── ⚙️ config/                  # Sistema de configuración
│   ├── __init__.py            # Punto de entrada unificado
│   ├── config.py              # Configuraciones legacy
│   ├── config_loader.py       # Carga de YAML
│   ├── backtest_config.py     # Config backtesting
│   ├── config.yaml            # Configuración YAML
│   └── mt5_config.yaml        # Config MT5
├── 📊 backtesting/            # Sistema de backtesting
│   ├── backtester.py          # Backtester base
│   └── advanced_backtester.py # Backtester avanzado
├── 🎯 strategies/             # Estrategias de trading
│   ├── ut_bot_psar.py         # Estrategia PSAR
│   ├── ut_bot_psar_conservative.py
│   ├── ut_bot_psar_optimized.py
│   └── optimized_strategy.py
├── 🛡️ risk_management/        # Gestión de riesgo
│   └── advanced_risk_manager.py
├── 📈 indicators/             # Indicadores técnicos
│   └── technical_indicators.py
├── 🔧 utils/                  # Utilidades
│   ├── logger.py              # Sistema de logging
│   ├── monitoring.py          # Monitoreo del sistema
│   ├── retry_manager.py       # Reintentos inteligentes
│   └── normalization.py       # Normalización de datos
├── 🧪 tests/                  # Tests del sistema
│   ├── test_new_features.py
│   └── test_ut_bot_psar.py
└── 📊 dashboard/              # Dashboard (futuro)
```

## 📦 Estructura del Proyecto

### **Módulos Core**
- **`core/`** - Núcleo del sistema con componentes esenciales
- **`config/`** - Sistema de configuración unificado y modular
- **`utils/`** - Utilidades y herramientas auxiliares

### **Funcionalidades**
- **`strategies/`** - Estrategias de trading implementadas
- **`backtesting/`** - Sistema completo de backtesting
- **`risk_management/`** - Gestión avanzada de riesgo
- **`indicators/`** - Indicadores técnicos y análisis

### **Datos y Almacenamiento**
- **`data/`** - Datos históricos y de mercado
- **`logs/`** - Registros del sistema
- **Sistema unificado** - SQLite + CSV integrado en `core/unified_storage.py`

## ⚙️ Configuración

### **Sistema Unificado de Configuración**

El sistema utiliza un enfoque unificado que integra todas las configuraciones:

```python
from config import (
    get_mt5_config,           # Configuración MT5
    get_backtest_config,      # Configuración backtesting
    get_strategy_config,      # Configuración estrategias
    get_risk_config,          # Configuración riesgo
    get_indicators_config,    # Configuración indicadores
    get_storage_config,       # Configuración almacenamiento
    get_normalization_config  # Configuración normalización
)

# Ejemplo de uso
mt5_config = get_mt5_config()
backtest_config = get_backtest_config()
```

### **Archivos de Configuración**

#### **`config.yaml`** - Configuración Principal
```yaml
system:
  log_level: INFO
  data_cache_dir: data/cache
  max_workers: 4

exchanges:
  bybit:
    api_key: "your_api_key"
    api_secret: "your_api_secret"
    sandbox: true

mt5:
  enabled: true
  server: "MetaQuotes-Demo"
  symbols: ["EURUSD", "GBPUSD", "USDJPY"]

backtesting:
  symbols: ["BTC/USDT", "ETH/USDT"]
  timeframe: "1h"
  initial_capital: 10000.0
```

#### **`mt5_config.yaml`** - Configuración MT5
```yaml
mt5:
  login: 12345678
  password: "password"
  server: "MetaQuotes-Demo"
  symbols: ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
  timeframes: ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
```

### **Configuración Programática**

```python
from core.config_manager import UnifiedConfig

# Configuración unificada
config = UnifiedConfig(
    system=SystemConfig(log_level="DEBUG"),
    mt5=MT5Config(enabled=True, server="MetaQuotes-Demo"),
    backtesting=BacktestingConfig(
        symbols=["BTC/USDT", "ETH/USDT"],
        initial_capital=10000.0
    )
)
```

## 🔧 Instalación

### **Requisitos del Sistema**
- **Python**: 3.8 o superior
- **RAM**: Mínimo 8GB, recomendado 16GB+
- **Almacenamiento**: 50GB+ para datos históricos
- **OS**: Windows 10+, Linux, macOS

### **Instalación Automática**

```bash
# Clonar el repositorio
git clone https://github.com/javiertarazon/botcopilot-sar.git
cd botcopilot-sar

# Crear entorno virtual
python -m venv trading_bot_env
trading_bot_env\Scripts\activate  # Windows
# source trading_bot_env/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

### **Dependencias Principales**
```
ccxt>=4.0.0          # Integración exchanges
pandas>=1.5.0        # Análisis de datos
numpy>=1.21.0        # Computación numérica
matplotlib>=3.5.0    # Gráficos
scipy>=1.7.0         # Estadísticas
scikit-learn>=1.0.0  # Machine Learning
pyyaml>=6.0          # Configuración YAML
```

### **Configuración MT5 (Opcional)**
```bash
# Instalar MetaTrader 5
# Descargar e instalar MT5 desde https://www.metatrader5.com/

# Configurar path en config.yaml
mt5:
  path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
```

## 📊 Uso del Sistema

### **Ejecución Básica**

```python
from main import main

### **Sistema de Almacenamiento Unificado**

```python
from utils.storage import DataStorage, save_to_csv, Trade
from core.unified_storage import UnifiedDataStorage
import pandas as pd

# Crear datos de ejemplo
trades_data = [
    Trade("BTCUSDT", pd.Timestamp("2024-01-01 10:00"), 
          pd.Timestamp("2024-01-01 11:00"), "long", 45000, 46000, 1.0, 1000, 2.22),
    Trade("ETHUSDT", pd.Timestamp("2024-01-01 12:00"), 
          pd.Timestamp("2024-01-01 13:00"), "short", 3000, 2950, 2.0, 1000, 3.33)
]

# Sistema de compatibilidad (funciona con código existente)
storage = DataStorage()
df_trades = pd.DataFrame([t.__dict__ for t in trades_data])

# Guardar datos
success = storage.save_to_sqlite(df_trades, "trades_table")
print(f"Datos guardados: {success}")

# Consultar datos
trades = storage.query_data("SELECT * FROM trades_table WHERE pnl > 0")
print(f"Trades ganadores: {len(trades) if trades is not None else 0}")

# Guardar en CSV
save_to_csv(df_trades, "data/trades_export.csv", storage)
```

### **Sistema Avanzado de Almacenamiento**

```python
from core.unified_storage import UnifiedDataStorage
from core.config_manager import StorageConfig

# Configurar almacenamiento avanzado
config = StorageConfig(
    sqlite_path="data/market_data.db",
    csv_path="data/csv_data",
    enable_sqlite=True,
    enable_csv=True
)

# Sistema unificado avanzado
unified_storage = UnifiedDataStorage(config)

# Guardar datos OHLCV
unified_storage.save_ohlcv_data("BTCUSDT", "1h", ohlcv_data)

# Cargar datos con filtros
data = unified_storage.load_ohlcv_data(
    "BTCUSDT", "1h", 
    start_date="2024-01-01", 
    end_date="2024-01-31"
)

# Verificar existencia de datos
exists = unified_storage.data_exists("BTCUSDT", "1h")
print(f"Datos disponibles: {exists}")
```

### **Backtesting**

```python
from backtesting.advanced_backtester import AdvancedBacktester
from config import get_backtest_config

# Configurar backtesting
config = get_backtest_config()
config.symbols = ["BTC/USDT", "ETH/USDT"]
config.start_date = "2024-01-01"
config.end_date = "2024-06-01"

# Ejecutar backtesting
backtester = AdvancedBacktester(config)
results = backtester.run_backtest()

print(f"Sharpe Ratio: {results.sharpe_ratio}")
print(f"Max Drawdown: {results.max_drawdown}")
print(f"Total Return: {results.total_return}")
```

### **Trading en Vivo**

```python
from strategies.ut_bot_psar import UTBotPSAR
from config import get_mt5_config, get_risk_config

# Configurar estrategia
mt5_config = get_mt5_config()
risk_config = get_risk_config()

strategy = UTBotPSAR(
    mt5_config=mt5_config,
    risk_config=risk_config
)

# Ejecutar estrategia
strategy.run()
```

## 🎯 Estrategias Implementadas

### **UT Bot PSAR**
Estrategia basada en Parabolic SAR con indicadores técnicos.

**Características:**
- Seguimiento de tendencias con PSAR
- Filtros de volatilidad
- Gestión de riesgo integrada
- Optimización automática de parámetros

```python
from strategies.ut_bot_psar import UTBotPSAR

strategy = UTBotPSAR(
    symbol="BTC/USDT",
    timeframe="1h",
    risk_per_trade=0.02
)
```

### **Estrategia Optimizada**
Versión avanzada con machine learning.

**Características:**
- Aprendizaje automático
- Adaptación dinámica al mercado
- Múltiples indicadores combinados
- Optimización bayesiana

### **Estrategias Conservadoras**
Versiones con menor riesgo para entornos volátiles.

## 📈 Sistema de Backtesting

### **Características Avanzadas**
- **Métricas Completas**: Sharpe, Sortino, Calmar, Win Rate
- **Análisis de Riesgo**: Value at Risk, Expected Shortfall
- **Optimización**: Grid Search, Random Search, Bayesian Optimization
- **Visualización**: Gráficos de equity, drawdown, retornos

### **Ejemplo de Backtesting**

```python
from backtesting.advanced_backtester import AdvancedBacktester

backtester = AdvancedBacktester()
backtester.load_data("BTC/USDT", "1h", "2024-01-01", "2024-06-01")

# Ejecutar estrategia
results = backtester.run_strategy(UTBotPSAR())

# Analizar resultados
backtester.analyze_results(results)
backtester.plot_results(results)
```

### **Optimización de Parámetros**

```python
from backtesting.parameter_optimizer import ParameterOptimizer

optimizer = ParameterOptimizer(UTBotPSAR())
best_params = optimizer.optimize(
    param_ranges={
        'psar_acceleration': (0.01, 0.1),
        'psar_maximum': (0.1, 0.5),
        'stop_loss': (0.01, 0.05)
    },
    metric='sharpe_ratio'
)
```

## 🛡️ Gestión de Riesgo

### **Características del Sistema**
- **Control de Drawdown**: Límite máximo configurable
- **Sizing de Posiciones**: Kelly Criterion, Fixed Percentage
- **Stop Loss Dinámico**: Basado en ATR, volatilidad
- **Diversificación**: Límite de correlación entre posiciones

### **Configuración de Riesgo**

```python
from risk_management.advanced_risk_manager import AdvancedRiskManager

risk_manager = AdvancedRiskManager(
    max_drawdown=0.15,        # 15% máximo drawdown
    max_positions=10,         # Máximo 10 posiciones
    position_size_percent=0.02,  # 2% por posición
    kelly_fraction=0.1        # 10% de Kelly
)

# Verificar si se puede abrir posición
if risk_manager.can_open_position(symbol, size, price):
    # Abrir posición
    risk_manager.open_position(symbol, size, price)
```

## 📊 Dashboard y Monitoreo

### **Características del Dashboard**
- **Monitoreo en Tiempo Real**: Posiciones abiertas, P&L
- **Métricas de Rendimiento**: Retornos, drawdown, Sharpe
- **Alertas**: Configurables por email, Telegram
- **Visualización**: Gráficos interactivos

### **Sistema de Logging**

```python
from utils.logger import setup_logger

logger = setup_logger("trading_bot", level="INFO")
logger.info("Estrategia iniciada")
logger.warning("Alerta de riesgo alto")
logger.error("Error de conexión")
```

## 🔍 Indicadores Técnicos

### **Indicadores Implementados**

#### **Volatilidad**
```python
from indicators.technical_indicators import VolatilityIndicator

volatility = VolatilityIndicator()
volatility_data = volatility.calculate(data, method='standard_deviation')
```

#### **Heikin-Ashi**
```python
from indicators.technical_indicators import HeikinAshiIndicator

heikin_ashi = HeikinAshiIndicator()
ha_data = heikin_ashi.calculate(data)
```

#### **Parabolic SAR**
```python
from indicators.technical_indicators import ParabolicSARIndicator

psar = ParabolicSARIndicator(acceleration=0.02, maximum=0.2)
psar_data = psar.calculate(data)
```

### **Sistema de Normalización**

```python
from utils.normalization import DataNormalizer

normalizer = DataNormalizer(method='minmax', feature_range=(0, 1))
normalized_data = normalizer.fit_transform(data)
```

## 💾 Almacenamiento de Datos

### ✅ **Sistema Unificado de Almacenamiento**
- **SQLite**: Base de datos relacional para datos estructurados
- **CSV**: Archivos planos para compatibilidad y análisis
- **Sistema híbrido**: Combinación óptima de ambos formatos
- **Compresión automática** y optimización de consultas
- **Validación de datos** integrada
- **Compatibilidad hacia atrás** con código existente

### ✅ **Interfaz Unificada**
```python
from utils.storage import DataStorage, save_to_csv, SimpleStorage, Trade
from core.unified_storage import UnifiedDataStorage

# Sistema unificado con compatibilidad hacia atrás
storage = DataStorage()  # Wrapper del sistema unificado
data = storage.query_data("SELECT * FROM trades WHERE symbol = ?", ("BTCUSDT",))

# Guardado en múltiples formatos
success = save_to_csv(data, "output/trades.csv", storage)

# Sistema avanzado
unified = UnifiedDataStorage(storage_config)
unified.save_ohlcv_data("BTCUSDT", "1h", ohlcv_data)
```

### ✅ **Características Avanzadas**
- **Validación automática** de timestamps y datos
- **Compresión inteligente** según tipo de datos
- **Índices automáticos** para consultas rápidas
- **Limpieza automática** de datos antiguos
- **Sincronización** entre SQLite y CSV
- **Métricas de rendimiento** integradas

## 🧪 Testing

### **Ejecutar Tests**

```bash
# Ejecutar todos los tests
python -m pytest tests/

# Ejecutar tests específicos
python -m pytest tests/test_ut_bot_psar.py -v

# Ejecutar con cobertura
python -m pytest --cov=src --cov-report=html
```

### **Test de Integración**

```python
from test_config_integration import main

# Ejecutar pruebas de integración
if __name__ == "__main__":
    main()
```

### **Tipos de Tests**
- **Unit Tests**: Componentes individuales
- **Integration Tests**: Interacción entre módulos
- **System Tests**: Funcionalidad completa
- **Performance Tests**: Rendimiento y optimización

## 📚 API Reference

### **Configuración**
```python
from config import (
    # Sistema unificado
    ConfigManager,
    UnifiedConfig,

    # Configuraciones específicas
    get_mt5_config(),
    get_backtest_config(),
    get_strategy_config(),
    get_risk_config(),
    get_indicators_config()
)
```

### **Estrategias**
```python
from strategies import (
    UTBotPSAR,
    UTBotPSARConservative,
    UTBotPSAROptimized,
    OptimizedStrategy
)
```

### **Backtesting**
```python
from backtesting import (
    AdvancedBacktester,
    Backtester,
    ParameterOptimizer
)
```

### **Indicadores**
```python
from indicators import (
    TechnicalIndicators,
    VolatilityIndicator,
    HeikinAshiIndicator,
    ParabolicSARIndicator
)
```

## 🔧 Desarrollo

### **Estructura de Desarrollo**
```
dev/
├── scripts/          # Scripts de desarrollo
├── notebooks/        # Jupyter notebooks
├── experiments/      # Experimentos
└── docs/            # Documentación
```

### **Contribuir**
1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

### **Estándares de Código**
- **PEP 8**: Estilo de código Python
- **Type Hints**: Anotaciones de tipos
- **Docstrings**: Documentación completa
- **Tests**: Cobertura > 80%

### **Pre-commit Hooks**
```bash
# Instalar pre-commit
pip install pre-commit
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

## 📝 Changelog

### **Versión 1.0.1** (Septiembre 2025)
- 🚀 **Integración Completa del Sistema de Almacenamiento Unificado**
  - ✅ Sistema híbrido SQLite + CSV operativo
  - ✅ Interfaz `IDataStorage` implementada en `UnifiedDataStorage`
  - ✅ Módulo de compatibilidad `utils/storage.py` para código legacy
  - ✅ Eliminación completa de archivos duplicados
  - ✅ Validación integrada de timestamps y datos
  - ✅ Compatibilidad total hacia atrás mantenida
  - ✅ Optimización automática según tipo de datos
  - ✅ Métricas de rendimiento integradas

- 🔧 **Mejoras de Arquitectura**
  - ✅ Resolución de dependencias circulares
  - ✅ Interfaz unificada para todos los sistemas de almacenamiento
  - ✅ Documentación actualizada con ejemplos de uso
  - ✅ Proyecto completamente limpio y optimizado

### **Versión 1.0.0** (Septiembre 2025)
- ✅ **Sistema Unificado de Configuración**
  - Configuración centralizada en `core/config_manager.py`
  - Compatibilidad hacia atrás completa
  - Integración de MT5, exchanges y estrategias

- ✅ **Estrategias Avanzadas**
  - UT Bot PSAR con múltiples variantes
  - Estrategia optimizada con ML
  - Sistema de indicadores técnicos completo

- ✅ **Backtesting Robusto**
  - Métricas avanzadas de rendimiento
  - Optimización de parámetros
  - Análisis de riesgo detallado

- ✅ **Gestión de Riesgo Inteligente**
  - Control de drawdown automático
  - Sizing óptimo de posiciones
  - Stop-loss dinámicos

- ✅ **Almacenamiento Optimizado**
  - Formatos eficientes (Parquet, HDF5)
  - Sistema de caché inteligente
  - Compresión automática

- ✅ **Arquitectura Modular**
  - Separación clara de responsabilidades
  - Componentes reutilizables
  - Fácil extensión y mantenimiento

## 🤝 Contribución

¡Las contribuciones son bienvenidas! Por favor, lee las [guías de contribución](CONTRIBUTING.md) para más detalles.

### **Áreas de Contribución**
- 🐛 **Bug Fixes**: Reportar y corregir errores
- ✨ **Features**: Nuevas funcionalidades
- 📚 **Documentation**: Mejorar documentación
- 🧪 **Tests**: Agregar tests
- 🎨 **UI/UX**: Mejorar interfaces

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 📞 Soporte

- 📧 **Email**: support@tradingbotcopilot.com
- 💬 **Discord**: [Unirse al servidor](https://discord.gg/tradingbot)
- 📖 **Documentación**: [docs.tradingbotcopilot.com](https://docs.tradingbotcopilot.com)
- 🐛 **Issues**: [GitHub Issues](https://github.com/javiertarazon/botcopilot-sar/issues)

---

**⚠️ Descargo de Responsabilidad**: Este software es para fines educativos e investigativos. El trading de criptomonedas implica riesgos significativos. No uses dinero real sin entender completamente los riesgos involucrados.

**⭐ Si te gusta este proyecto, ¡dale una estrella en GitHub!**</content>
<parameter name="filePath">c:\Users\javie\proyecto bot copilot\bot trader copilot version 1.0\descarga_datos\README.md
