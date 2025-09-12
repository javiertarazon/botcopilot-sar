# 🤝 Guía de Contribución - Trading Bot Copilot

¡Gracias por tu interés en contribuir al **Trading Bot Copilot**! Este documento explica cómo puedes contribuir al proyecto de manera efectiva.

## 📋 Tabla de Contenidos

- [🚀 Primeros Pasos](#-primeros-pasos)
- [🐛 Reportar Bugs](#-reportar-bugs)
- [✨ Solicitar Features](#-solicitar-features)
- [🛠️ Desarrollo](#️-desarrollo)
- [📝 Estándares de Código](#-estándares-de-código)
- [🧪 Testing](#-testing)
- [📚 Documentación](#-documentación)
- [🔄 Pull Requests](#-pull-requests)
- [🎯 Áreas de Contribución](#-áreas-de-contribución)

## 🚀 Primeros Pasos

### **1. Configurar el Entorno de Desarrollo**

```bash
# Clonar el repositorio
git clone https://github.com/javiertarazon/botcopilot-sar.git
cd botcopilot-sar

# Crear rama de desarrollo
git checkout -b development

# Crear entorno virtual
python -m venv trading_bot_env
source trading_bot_env/bin/activate  # Linux/Mac
# trading_bot_env\Scripts\activate   # Windows

# Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Instalar pre-commit hooks
pre-commit install
```

### **2. Configurar Pre-commit**

```bash
# Instalar pre-commit
pip install pre-commit

# Configurar hooks
pre-commit install

# Ejecutar en todos los archivos
pre-commit run --all-files
```

### **3. Verificar Instalación**

```bash
# Ejecutar tests básicos
python -m pytest tests/test_config_integration.py -v

# Verificar linting
flake8 src/ tests/

# Verificar tipos
mypy src/
```

## 🐛 Reportar Bugs

### **Plantilla de Bug Report**

```markdown
**Título:** [BUG] Descripción breve del problema

**Descripción:**
Descripción detallada del bug y cómo reproducirlo.

**Pasos para Reproducir:**
1. Ir a '...'
2. Ejecutar '....'
3. Ver error

**Comportamiento Esperado:**
Qué debería suceder.

**Comportamiento Actual:**
Qué está sucediendo.

**Entorno:**
- OS: [Windows/Linux/Mac]
- Python: [3.8/3.9/3.10/3.11]
- Versión del Bot: [1.0.0]

**Logs/Error:**
```
Pegar logs relevantes aquí
```

**Contexto Adicional:**
Cualquier información adicional relevante.
```

### **Etiquetas para Bugs**
- `bug` - Error en el código
- `critical` - Bug crítico que impide funcionamiento
- `enhancement` - Mejora o nueva funcionalidad
- `documentation` - Problema de documentación
- `good first issue` - Bueno para principiantes

## ✨ Solicitar Features

### **Plantilla de Feature Request**

```markdown
**Título:** [FEATURE] Nombre de la funcionalidad

**Problema:**
Descripción del problema que esta funcionalidad resolvería.

**Solución Propuesta:**
Descripción detallada de la funcionalidad propuesta.

**Alternativas Consideradas:**
Otras soluciones que se consideraron.

**Impacto:**
Cómo afectaría esta funcionalidad al sistema existente.

**Prioridad:**
[Alta/Media/Baja]

**Tiempo Estimado:**
Estimación de tiempo para implementar.
```

## 🛠️ Desarrollo

### **Estructura de Ramas**

```
main                    # Rama principal (producción)
├── development         # Rama de desarrollo
│   ├── feature/*       # Nuevas funcionalidades
│   ├── bugfix/*        # Corrección de bugs
│   ├── refactor/*      # Refactorización
│   └── docs/*          # Documentación
```

### **Flujo de Trabajo Git**

```bash
# Crear rama para nueva funcionalidad
git checkout -b feature/nueva-funcionalidad

# Hacer commits pequeños y descriptivos
git commit -m "feat: agregar nueva funcionalidad X"

# Mantener rama actualizada
git fetch origin
git rebase origin/development

# Push a rama
git push origin feature/nueva-funcionalidad
```

### **Convenciones de Commit**

```
feat: nueva funcionalidad
fix: corrección de bug
docs: cambios en documentación
style: cambios de formato
refactor: refactorización de código
test: agregar o modificar tests
chore: cambios de mantenimiento
```

## 📝 Estándares de Código

### **Python Style Guide (PEP 8)**

```python
# ✅ Correcto
def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    """Calculate Sharpe ratio for given returns."""
    excess_returns = returns - risk_free_rate
    return excess_returns.mean() / excess_returns.std()

# ❌ Incorrecto
def calculate_sharpe_ratio(returns,risk_free_rate=0.02):
    excess_returns=returns-risk_free_rate
    return excess_returns.mean()/excess_returns.std()
```

### **Type Hints**

```python
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np

def calculate_returns(prices: pd.Series,
                     method: str = "simple") -> pd.Series:
    """Calculate returns from price series."""
    if method == "simple":
        return prices.pct_change()
    elif method == "log":
        return np.log(prices / prices.shift(1))
    else:
        raise ValueError(f"Unknown method: {method}")
```

### **Docstrings**

```python
def calculate_volatility(prices: pd.Series,
                        window: int = 20,
                        method: str = "std") -> pd.Series:
    """
    Calculate rolling volatility of price series.

    Args:
        prices: Price series
        window: Rolling window size
        method: Volatility calculation method ('std', 'parkinson', etc.)

    Returns:
        Rolling volatility series

    Raises:
        ValueError: If method is not supported

    Examples:
        >>> prices = pd.Series([100, 101, 102, 103, 102])
        >>> vol = calculate_volatility(prices, window=3)
        >>> print(vol.tail())
    """
    if method == "std":
        return prices.rolling(window).std()
    elif method == "parkinson":
        # Implementación de Parkinson
        pass
    else:
        raise ValueError(f"Unsupported method: {method}")
```

### **Nombres de Variables y Funciones**

```python
# ✅ Correcto
def calculate_portfolio_returns(weights, returns):
    portfolio_return = np.sum(weights * returns, axis=1)
    return portfolio_return

# ❌ Incorrecto
def calc_port_ret(w, r):
    pr = np.sum(w * r, axis=1)
    return pr
```

## 🧪 Testing

### **Estructura de Tests**

```
tests/
├── unit/              # Tests unitarios
├── integration/       # Tests de integración
├── system/           # Tests del sistema completo
├── fixtures/         # Datos de prueba
└── conftest.py       # Configuración de pytest
```

### **Ejemplo de Test Unitario**

```python
import pytest
import pandas as pd
import numpy as np
from src.indicators.volatility import calculate_volatility

class TestVolatilityCalculation:
    """Test cases for volatility calculations."""

    def test_calculate_volatility_std(self):
        """Test standard deviation volatility calculation."""
        prices = pd.Series([100, 101, 102, 103, 102, 101])
        vol = calculate_volatility(prices, window=3, method="std")

        # Verificar que no hay NaN en resultados válidos
        assert not vol.isna().all()

        # Verificar cálculo manual
        expected = prices.rolling(3).std()
        pd.testing.assert_series_equal(vol, expected)

    def test_calculate_volatility_invalid_method(self):
        """Test that invalid method raises ValueError."""
        prices = pd.Series([100, 101, 102])

        with pytest.raises(ValueError, match="Unsupported method"):
            calculate_volatility(prices, method="invalid")

    @pytest.mark.parametrize("window", [2, 5, 10])
    def test_calculate_volatility_different_windows(self, window):
        """Test volatility calculation with different window sizes."""
        prices = pd.Series(range(100))
        vol = calculate_volatility(prices, window=window)

        # Verificar que la longitud es correcta
        assert len(vol) == len(prices)

        # Verificar que los primeros window-1 valores son NaN
        assert vol.iloc[:window-1].isna().all()
```

### **Ejecutar Tests**

```bash
# Ejecutar todos los tests
pytest

# Ejecutar tests específicos
pytest tests/unit/test_volatility.py

# Ejecutar con cobertura
pytest --cov=src --cov-report=html

# Ejecutar tests marcados
pytest -m "slow"  # Tests marcados como lentos
pytest -m "integration"  # Tests de integración
```

### **Cobertura de Código**

```bash
# Generar reporte de cobertura
pytest --cov=src --cov-report=html

# Ver reporte en navegador
# Abrir htmlcov/index.html
```

## 📚 Documentación

### **Documentación del Código**

```python
"""
Trading Bot Copilot - Sistema de Trading Automatizado
====================================================

Módulo de indicadores técnicos.

Este módulo proporciona implementaciones eficientes de indicadores
técnicos comunes utilizados en análisis de trading.
"""

class TechnicalIndicators:
    """
    Clase base para indicadores técnicos.

    Proporciona métodos comunes y utilidades para el cálculo
    de indicadores técnicos en series de precios.
    """

    def __init__(self, data: pd.DataFrame):
        """
        Inicializar indicador técnico.

        Args:
            data: DataFrame con columnas OHLCV
        """
        self.data = data
        self._validate_data()

    def _validate_data(self) -> None:
        """Validar que los datos tengan el formato correcto."""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns
                          if col not in self.data.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
```

### **README y Documentación**

- Mantener README.md actualizado
- Documentar nuevas funcionalidades
- Proporcionar ejemplos de uso
- Incluir requisitos y dependencias

## 🔄 Pull Requests

### **Plantilla de PR**

```markdown
## Descripción
Breve descripción de los cambios realizados.

## Tipo de Cambio
- [ ] 🐛 Bug fix
- [ ] ✨ Nueva funcionalidad
- [ ] 💥 Breaking change
- [ ] 📚 Documentación
- [ ] 🎨 Estilo de código
- [ ] ♻️ Refactorización

## Checklist
- [ ] Tests agregados/modificados
- [ ] Documentación actualizada
- [ ] Código sigue estándares PEP 8
- [ ] Type hints incluidos
- [ ] Cobertura de tests > 80%
- [ ] Pre-commit hooks pasan

## Testing
```bash
# Comandos para probar los cambios
pytest tests/test_new_feature.py
```

## Issues Relacionados
- Closes #123
- Relates to #456

## Screenshots (si aplica)
[Agregar screenshots de cambios visuales]
```

### **Revisión de Código**

**Para Revisores:**
- Verificar que el código sigue estándares
- Comprobar que tests pasan
- Revisar lógica y algoritmos
- Verificar documentación
- Considerar impacto en performance

**Para Contribuidores:**
- Responder comentarios de revisión
- Hacer cambios solicitados
- Mantener conversación constructiva
- Aprender de feedback

## 🎯 Áreas de Contribución

### **🔰 Para Principiantes**

1. **Corrección de Typos**
   - Revisar documentación
   - Corregir errores ortográficos

2. **Mejoras de Documentación**
   - Agregar ejemplos
   - Mejorar docstrings
   - Traducir documentación

3. **Tests Adicionales**
   - Agregar tests unitarios
   - Mejorar cobertura
   - Tests de edge cases

### **🧪 Testing y QA**

1. **Framework de Testing**
   - Mejorar fixtures
   - Agregar tests de integración
   - Tests de performance

2. **CI/CD**
   - Mejorar GitHub Actions
   - Agregar más checks
   - Automatizar releases

### **⚡ Performance**

1. **Optimización**
   - Mejorar algoritmos
   - Optimizar uso de memoria
   - Paralelización

2. **Benchmarking**
   - Crear benchmarks
   - Comparar performance
   - Identificar bottlenecks

### **🎨 UI/UX**

1. **Dashboard**
   - Mejorar interfaz
   - Agregar nuevas visualizaciones
   - UX improvements

2. **Logging y Monitoreo**
   - Mejorar logs
   - Dashboard de métricas
   - Alertas inteligentes

### **🔧 Core Features**

1. **Nuevas Estrategias**
   - Implementar estrategias populares
   - Crear estrategias custom
   - Backtesting avanzado

2. **Nuevos Indicadores**
   - Indicadores técnicos
   - Indicadores custom
   - Machine learning indicators

3. **Integraciones**
   - Nuevos exchanges
   - APIs de datos
   - Servicios de notificación

### **📊 Data Science**

1. **Machine Learning**
   - Modelos de predicción
   - Feature engineering
   - Validación de modelos

2. **Análisis Avanzado**
   - Risk analytics
   - Portfolio optimization
   - Statistical arbitrage

## 📞 Comunicación

- **GitHub Issues**: Para bugs y features
- **GitHub Discussions**: Para preguntas generales
- **Discord**: Para chat en tiempo real
- **Email**: Para asuntos privados

## 🎉 Reconocimiento

¡Todos los contribuidores serán reconocidos!
- Mención en CHANGELOG.md
- Créditos en documentación
- Posible mención en releases

## 📋 Código de Conducta

Este proyecto sigue un código de conducta para asegurar un entorno inclusivo y respetuoso para todos los contribuidores.

### **Normas Básicas**
- Sé respetuoso con otros contribuidores
- Usa lenguaje inclusivo
- Acepta feedback constructivo
- Enfócate en el mérito técnico
- Reporta comportamiento inapropiado

---

¡Gracias por contribuir al **Trading Bot Copilot**! 🚀

Tu contribución ayuda a mejorar el sistema para toda la comunidad de traders.

**⭐ Si encuentras útil este proyecto, ¡dale una estrella en GitHub!**</content>
<parameter name="filePath">c:\Users\javie\proyecto bot copilot\bot trader copilot version 1.0\descarga_datos\CONTRIBUTING.md
