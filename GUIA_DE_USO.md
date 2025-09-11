# 🚀 Guía de Uso - Bot Trader Copilot

## 📋 Descripción del Sistema

El **Bot Trader Copilot** es un sistema automatizado de trading que:

1. **Descarga datos** de múltiples fuentes (criptomonedas y acciones)
2. **Aplica análisis técnico** con indicadores profesionales
3. **Ejecuta estrategias** basadas en UT Bot + Parabolic SAR
4. **Realiza backtesting** con métricas detalladas
5. **Presenta resultados** en un dashboard interactivo

## 🎯 ¿Cómo Funciona?

### 1. **Detección Automática de Activos**
```python
# El sistema identifica automáticamente el tipo de activo:
"BTC/USDT"  → Criptomoneda (usa CCXT/Bybit)
"AAPL.US"   → Acción (usa MetaTrader 5)
```

### 2. **Procesamiento Asíncrono**
- Descarga **múltiples símbolos simultáneamente**
- **Calcula indicadores técnicos** (PSAR, ATR, ADX, EMAs)
- **Ejecuta 3 estrategias** en paralelo por símbolo

### 3. **Estrategias Incluidas**
- **🛡️ Conservadora**: Menor riesgo, trades más selectivos
- **⚖️ Básica**: Balance entre riesgo y rentabilidad
- **🚀 Optimizada**: Mayor agresividad, más oportunidades

## ⚙️ Configuración Rápida

### 📁 Archivo Principal: `descarga_datos/config/config.yaml`

```yaml
# Símbolos a analizar
backtesting:
  symbols:
    - "BTC/USDT"    # Criptomonedas
    - "ETH/USDT"
    - "AAPL.US"     # Acciones
    - "TSLA.US"
  
  # Configuración temporal
  timeframe: "1h"           # 1 hora (recomendado)
  start_date: "2023-01-01"  # Fecha inicio
  end_date: "2025-06-01"    # Fecha fin
  
  # Configuración financiera
  initial_capital: 10000    # Capital inicial
  commission: 0.1           # Comisión por trade (%)
  
  # Estrategias activas
  strategies:
    Estrategia_Basica: true        # ✅ Activa
    Estrategia_Conservadora: true  # ✅ Activa
    Estrategia_Optimizada: true    # ✅ Activa

# Dashboard automático
system:
  auto_launch_dashboard: true  # ✅ Se abre automáticamente
```

## 🚀 Ejecutar el Sistema

### 1. **Preparación**
```bash
# Navegar al directorio
cd botcopilot-sar/descarga_datos

# Verificar configuración (opcional)
python -c "from config.config_loader import load_config_from_yaml; print('Config OK')"
```

### 2. **Ejecución**
```bash
# Ejecutar backtesting completo
python main.py
```

### 3. **Proceso Automático**
El sistema ejecuta automáticamente:
1. ✅ **Inicialización** de componentes
2. 📥 **Descarga** de datos históricos  
3. 📊 **Cálculo** de indicadores técnicos
4. 🎯 **Ejecución** de estrategias de trading
5. 📈 **Backtesting** y cálculo de métricas
6. 💾 **Almacenamiento** de resultados
7. 🌐 **Lanzamiento** automático del dashboard

## 📊 Interpretación de Resultados

### 🏆 Dashboard Automático
Al finalizar, se abre automáticamente en: **http://localhost:8501**

**Métricas Principales:**
- **P&L Total**: Ganancia/pérdida total en $
- **Win Rate**: % de trades ganadores
- **Max Drawdown**: Máxima caída del capital
- **Sharpe Ratio**: Rendimiento ajustado por riesgo
- **Total Trades**: Número de operaciones

### 📈 Interpretación de Números

**✅ Resultado Positivo:**
```
NVDA.US | Estrategia_Optimizada | $8,231.66 | 50.0% | 8.2%
         ↑                       ↑           ↑       ↑
      Símbolo                 Ganancia   Win Rate  Max DD
```

**❌ Resultado Negativo:**
```
XRP/USDT | Estrategia_Basica | -$245.30 | 35.2% | 15.8%
```

### 🎯 ¿Qué Buscar?

**🟢 Buenos Resultados:**
- P&L > $0 (rentable)
- Win Rate > 45%
- Max Drawdown < 15%
- Sharpe Ratio > 0.5

**🔴 Señales de Alerta:**
- P&L muy negativo
- Win Rate < 30%
- Max Drawdown > 25%
- Muchos trades (sobretrading)

## 🎛️ Personalización Avanzada

### 1. **Modificar Símbolos**
```yaml
# En config.yaml
backtesting:
  symbols:
    # Agregar más criptos
    - "DOGE/USDT"
    - "ADA/USDT"
    # Agregar más acciones  
    - "GOOGL.US"
    - "MSFT.US"
```

### 2. **Cambiar Timeframe**
```yaml
timeframe: "4h"    # 4 horas (menos trades, más estables)
timeframe: "15m"   # 15 minutos (más trades, más volátiles)
```

### 3. **Ajustar Período**
```yaml
start_date: "2024-01-01"  # Solo datos recientes
end_date: "2024-12-31"    # Período específico
```

### 4. **Configurar Capital**
```yaml
initial_capital: 50000  # $50,000 iniciales
commission: 0.05        # Comisión más baja
```

## 🔧 Resolución de Problemas

### ❌ Error: "No module named 'pandas'"
```bash
# Instalar dependencias
pip install pandas numpy ccxt PyYAML streamlit plotly
```

### ❌ Error: "MT5 not available"
- **Normal**: El sistema usa datos demo si MT5 no está disponible
- **Solución**: Solo afecta acciones, criptos funcionan normalmente

### ❌ Dashboard no se abre
```bash
# Ejecutar manualmente
cd ..  # Volver al directorio principal
python run_dashboard.py
# O usar Streamlit directamente
streamlit run dashboard.py
```

### ❌ Error de conexión CCXT
- **Normal**: Usa datos de ejemplo si no hay API keys
- **Solución**: Configurar API keys de Bybit/Binance (opcional)

### ❌ Puerto 8501 ocupado
```bash
# El sistema limpia automáticamente puertos ocupados
# Si persiste, reiniciar o cambiar puerto en config
```

## 🎯 Estrategias Explicadas

### 🛡️ **Conservadora**
- **Objetivo**: Preservar capital
- **Características**: Pocos trades, stop loss pequeño
- **Ideal para**: Perfiles de bajo riesgo

### ⚖️ **Básica**
- **Objetivo**: Balance riesgo/recompensa
- **Características**: Configuración estándar
- **Ideal para**: Mayoría de usuarios

### 🚀 **Optimizada**  
- **Objetivo**: Maximizar rendimiento
- **Características**: Más trades, mayor take profit
- **Ideal para**: Perfiles agresivos

## 📈 Mejores Prácticas

### ✅ **Recomendaciones**
1. **Empezar con timeframe 1h** (más estable)
2. **Usar período de 1-2 años** (datos suficientes)
3. **Probar con pocos símbolos** primero
4. **Revisar Max Drawdown** antes que P&L
5. **Comparar estrategias** en el dashboard

### ⚠️ **Precauciones**
1. **Backtesting ≠ Futuro**: Resultados pasados no garantizan futuros
2. **Demo Data**: Sistema usa datos de ejemplo sin APIs
3. **No es asesoría financiera**: Solo herramienta educativa
4. **Validar siempre**: Verificar resultados manualmente

## 🎯 Casos de Uso

### 📚 **Educativo**
- Aprender análisis técnico
- Entender estrategias de trading
- Practicar interpretación de métricas

### 🔬 **Investigación**
- Probar nuevas estrategias
- Comparar diferentes timeframes
- Analizar comportamiento de activos

### 🛠️ **Desarrollo**
- Base para sistemas más complejos
- Prototipado de estrategias
- Validación de conceptos

## 🚀 Próximos Pasos

### 🎯 **Después del Backtesting**
1. **Analizar resultados** en dashboard
2. **Identificar mejores símbolos/estrategias**
3. **Ajustar configuración** si es necesario
4. **Probar diferentes períodos**
5. **Documentar aprendizajes**

### 🔄 **Mejoras Futuras**
- Trading en vivo (paper trading)
- Más estrategias (MACD, RSI, etc.)
- Machine learning
- Notificaciones automáticas
- Optimización de parámetros

---

**🤖 ¡Disfruta explorando el mundo del trading automatizado con Bot Trader Copilot!**

> **Recuerda**: Este es un sistema educativo y de investigación. Siempre valida los resultados y consulta con profesionales antes de invertir dinero real.