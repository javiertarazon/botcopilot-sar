#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Profesional de Backtesting - Bot Trader Copilot
Interfaz web para visualizar métricas completas y gráficos del balance final
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime
import sqlite3
from pathlib import Path

# Configuración de la página
st.set_page_config(
    page_title="Bot Trader Copilot - Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Función para verificar que estamos en el directorio correcto
def setup_paths():
    """Configura las rutas correctas para los datos"""
    # Intentar múltiples ubicaciones posibles para los datos
    possible_data_dirs = [
        "../data/dashboard_results",  # Desde dashboard/ hacia data/dashboard_results/
        "../../data/dashboard_results",  # Desde subdirectorio
        "./data/dashboard_results",  # Ruta relativa
        "data/dashboard_results",  # Ruta simple
        "../data",  # Directorio de datos principal
    ]

    for data_dir in possible_data_dirs:
        if os.path.exists(data_dir):
            st.sidebar.success(f"Datos encontrados en: {data_dir}")
            return data_dir

    # Si no se encuentra, mostrar error pero continuar
    st.sidebar.error("No se encontraron datos de backtesting")
    st.sidebar.info("Ejecuta el backtesting primero para generar los datos")
    return None

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(45deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .metric-label {
        font-size: 1rem;
        opacity: 0.9;
    }
    .sidebar-header {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

class BacktestDashboard:
    """Dashboard profesional para visualizar resultados de backtesting"""

    def __init__(self):
        # Configurar rutas de manera más robusta
        self.data_path = self._find_data_path()
        self.db_path = self.data_path / "market_data.db" if self.data_path else None
        self.csv_path = self.data_path / "csv" if self.data_path else None

    def _find_data_path(self):
        """Encuentra la ruta correcta a los datos"""
        # Posibles ubicaciones de los datos
        possible_paths = [
            Path(__file__).parent.parent / "data",  # Desde dashboard/ hacia descarga_datos/data/
            Path(__file__).parent.parent / "data" / "dashboard_results",  # Ruta específica de resultados
            Path("../data"),  # Desde el directorio del dashboard
            Path("../../data"),  # Desde subdirectorio
            Path("./data"),  # Ruta relativa
            Path("data"),  # Ruta simple
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # Si no se encuentra, intentar con rutas absolutas del proyecto
        script_dir = Path(__file__).parent
        project_root = script_dir.parent

        absolute_paths = [
            project_root / "data",
            project_root / "data" / "dashboard_results",
        ]

        for path in absolute_paths:
            if path.exists():
                return path

        return None

    def load_backtest_results(self):
        """Carga los resultados del backtesting desde archivos JSON"""
        results = {}

        # Cargar datos REALES desde JSON
        dashboard_results_path = self.data_path / "dashboard_results"
        if dashboard_results_path.exists():
            # Cargar resumen global si existe
            global_summary_file = dashboard_results_path / "global_summary.json"
            if global_summary_file.exists():
                try:
                    with open(global_summary_file, 'r', encoding='utf-8') as f:
                        global_data = json.load(f)

                    # Cargar datos individuales de cada símbolo
                    for symbol_file in dashboard_results_path.glob("*_results.json"):
                        if symbol_file.name != "global_summary.json":
                            try:
                                with open(symbol_file, 'r', encoding='utf-8') as f:
                                    symbol_data = json.load(f)

                                symbol = symbol_data['symbol']
                                results[symbol] = symbol_data['strategies']

                                # Agregar métricas de compensación al símbolo
                                for strategy_name, strategy_result in symbol_data['strategies'].items():
                                    # Asegurar que las métricas de compensación estén presentes
                                    if 'compensated_trades' not in strategy_result:
                                        strategy_result['compensated_trades'] = 0
                                    if 'total_compensation_pnl' not in strategy_result:
                                        strategy_result['total_compensation_pnl'] = 0.0
                                    if 'compensation_success_rate' not in strategy_result:
                                        strategy_result['compensation_success_rate'] = 0.0
                                    if 'adjusted_total_pnl' not in strategy_result:
                                        strategy_result['adjusted_total_pnl'] = strategy_result.get('total_pnl', 0)

                            except Exception as e:
                                st.error(f"Error cargando {symbol_file}: {e}")

                    if results:
                        st.success(f"✅ Datos reales cargados desde {len(results)} símbolos")
                        return results
                    else:
                        st.error("❌ No se encontraron datos válidos en los archivos JSON")
                        return None

                except Exception as e:
                    st.error(f"Error cargando resumen global: {e}")
                    return None
        
        # Si no hay datos reales, mostrar error
        st.error("❌ No se encontraron resultados de backtesting. Ejecuta main.py primero para generar datos reales.")
        st.info("💡 Para generar resultados: ejecuta 'python main.py' en el directorio del proyecto")
        return None

    def create_summary_metrics(self, results):
        """Crea métricas resumen"""
        if not results:
            return {
                'total_symbols': 0,
                'profitable_symbols': 0,
                'total_pnl': 0,
                'total_trades': 0,
                'avg_win_rate': 0,
                'best_symbol': 'N/A'
            }

        total_pnl = 0
        total_trades = 0
        profitable_symbols = 0
        win_rates = []
        best_symbol = None
        best_pnl = float('-inf')

        # === VARIABLES PARA COMPENSACIÓN ===
        total_compensated_trades = 0
        total_compensation_pnl = 0.0
        compensation_rates = []
        sharpe_ratios = []
        kelly_usages = []
        correlation_adjustments = []
        volatility_adjustments = []
        risk_scores = []

        for symbol, symbol_data in results.items():
            # Verificar si symbol_data es un diccionario con estrategias
            if isinstance(symbol_data, dict) and symbol_data:
                # Si tiene estrategias como claves
                if any(isinstance(v, dict) and 'total_pnl' in v for v in symbol_data.values()):
                    try:
                        best_strategy = max(symbol_data.items(), key=lambda x: x[1].get('total_pnl', 0))
                        strategy_name, result = best_strategy

                        pnl = result.get('total_pnl', 0)
                        trades = result.get('total_trades', 0)
                        win_rate = result.get('win_rate', 0)

                        # === MÉTRICAS DE COMPENSACIÓN ===
                        compensated_trades = result.get('compensated_trades', 0)
                        compensation_pnl = result.get('total_compensation_pnl', 0.0)
                        compensation_rate = result.get('compensation_success_rate', 0.0)

                        # === MÉTRICAS AVANZADAS DE RIESGO ===
                        sharpe_ratio = result.get('sharpe_ratio', 0.0)
                        kelly_usage = result.get('avg_kelly_usage', 0.0)
                        correlation_adjustment = result.get('avg_correlation_adjustment', 1.0)
                        volatility_adjustment = result.get('avg_volatility_adjustment', 0.0)
                        risk_score = result.get('avg_risk_score', 0.0)

                        total_pnl += pnl
                        total_trades += trades
                        if win_rate > 0:
                            win_rates.append(win_rate)

                        # Agregar métricas de compensación
                        total_compensated_trades += compensated_trades
                        total_compensation_pnl += compensation_pnl
                        if compensation_rate > 0:
                            compensation_rates.append(compensation_rate)

                        # Agregar métricas avanzadas de riesgo
                        if sharpe_ratio != 0:
                            sharpe_ratios.append(sharpe_ratio)
                        if kelly_usage > 0:
                            kelly_usages.append(kelly_usage)
                        if correlation_adjustment != 1.0:
                            correlation_adjustments.append(correlation_adjustment)
                        if volatility_adjustment > 0:
                            volatility_adjustments.append(volatility_adjustment)
                        if risk_score > 0:
                            risk_scores.append(risk_score)

                        if pnl > 0:
                            profitable_symbols += 1

                        if pnl > best_pnl:
                            best_pnl = pnl
                            best_symbol = symbol
                    except (KeyError, TypeError, ValueError) as e:
                        st.warning(f"Error procesando {symbol}: {e}")
                        continue
                else:
                    # Si symbol_data es directamente las métricas
                    try:
                        pnl = symbol_data.get('total_pnl', symbol_data.get('pnl', 0))
                        trades = symbol_data.get('total_trades', symbol_data.get('trades', 0))
                        win_rate = symbol_data.get('win_rate', 0)

                        # === MÉTRICAS DE COMPENSACIÓN ===
                        compensated_trades = symbol_data.get('compensated_trades', 0)
                        compensation_pnl = symbol_data.get('total_compensation_pnl', 0.0)
                        compensation_rate = symbol_data.get('compensation_success_rate', 0.0)

                        # === MÉTRICAS AVANZADAS DE RIESGO ===
                        sharpe_ratio = symbol_data.get('sharpe_ratio', 0.0)
                        kelly_usage = symbol_data.get('avg_kelly_usage', 0.0)
                        correlation_adjustment = symbol_data.get('avg_correlation_adjustment', 1.0)
                        volatility_adjustment = symbol_data.get('avg_volatility_adjustment', 0.0)
                        risk_score = symbol_data.get('avg_risk_score', 0.0)

                        total_pnl += pnl
                        total_trades += trades
                        if win_rate > 0:
                            win_rates.append(win_rate)

                        # Agregar métricas de compensación
                        total_compensated_trades += compensated_trades
                        total_compensation_pnl += compensation_pnl
                        if compensation_rate > 0:
                            compensation_rates.append(compensation_rate)

                        # Agregar métricas avanzadas de riesgo
                        if sharpe_ratio != 0:
                            sharpe_ratios.append(sharpe_ratio)
                        if kelly_usage > 0:
                            kelly_usages.append(kelly_usage)
                        if correlation_adjustment != 1.0:
                            correlation_adjustments.append(correlation_adjustment)
                        if volatility_adjustment > 0:
                            volatility_adjustments.append(volatility_adjustment)
                        if risk_score > 0:
                            risk_scores.append(risk_score)

                        if pnl > 0:
                            profitable_symbols += 1

                        if pnl > best_pnl:
                            best_pnl = pnl
                            best_symbol = symbol
                    except (KeyError, TypeError, ValueError) as e:
                        st.warning(f"Error procesando {symbol}: {e}")
                        continue
            else:
                st.warning(f"Estructura de datos inválida para {symbol}")
                continue

        # Calcular promedio de tasa de compensación
        avg_compensation_rate = np.mean(compensation_rates) if compensation_rates else 0.0

        # Calcular promedios de métricas avanzadas de riesgo
        avg_sharpe_ratio = np.mean(sharpe_ratios) if sharpe_ratios else 0.0
        avg_kelly_usage = np.mean(kelly_usages) if kelly_usages else 0.0
        avg_correlation_adjustment = np.mean(correlation_adjustments) if correlation_adjustments else 1.0
        avg_volatility_adjustment = np.mean(volatility_adjustments) if volatility_adjustments else 0.0
        avg_risk_score = np.mean(risk_scores) if risk_scores else 0.0

        # Calcular promedio de win rate
        avg_win_rate = np.mean(win_rates) if win_rates else 0.0

        return {
            'total_symbols': len(results),
            'profitable_symbols': profitable_symbols,
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'avg_win_rate': avg_win_rate,
            'avg_sharpe_ratio': avg_sharpe_ratio,
            'avg_kelly_usage': avg_kelly_usage,
            'avg_correlation_adjustment': avg_correlation_adjustment,
            'avg_volatility_adjustment': avg_volatility_adjustment,
            'avg_risk_score': avg_risk_score,
            'best_symbol': best_symbol or 'N/A',
            'total_compensated_trades': total_compensated_trades,
            'total_compensation_pnl': total_compensation_pnl,
            'avg_compensation_rate': avg_compensation_rate
        }
    """Función principal del dashboard"""

def main():
    # DIAGNÓSTICO DEL SISTEMA
    st.sidebar.markdown('<div class="sidebar-header">🔍 Diagnóstico del Sistema</div>', unsafe_allow_html=True)

    # Verificar rutas de datos
    data_path = None
    possible_data_dirs = [
        Path(r"c:\Users\javie\proyecto bot copilot\bot trader copilot version 1.0\descarga_datos\data\dashboard_results"),  # Ruta corregida principal
        Path("../descarga_datos/data/dashboard_results"),
        Path("../../descarga_datos/data/dashboard_results"),
        Path("./data/dashboard_results"),
        Path("data/dashboard_results"),
    ]

    for path in possible_data_dirs:
        if path.exists():
            data_path = path
            st.sidebar.success(f"✅ Datos encontrados en: {path}")
            break

    if not data_path:
        st.sidebar.error("❌ No se encontraron datos de backtesting")
        st.sidebar.info("Ejecuta main.py primero para generar datos")

        # Mostrar error en pantalla principal
        st.error("🚨 No se encontraron datos de backtesting")
        st.info("**Para generar datos:**")
        st.code("cd 'bot trader copilot version 1.0/descarga_datos'")
        st.code("python main.py")
        st.info("Los datos se guardarán en: `data/dashboard_results/`")
        return

    # Mostrar archivos disponibles
    json_files = list(data_path.glob("*.json"))
    st.sidebar.write(f"**Archivos encontrados:** {len(json_files)}")
    for file in json_files[:3]:  # Mostrar primeros 3
        st.sidebar.write(f"• {file.name}")
    if len(json_files) > 3:
        st.sidebar.write(f"... y {len(json_files) - 3} más")

    # Inicializar dashboard
    dashboard = BacktestDashboard()

    # Cargar resultados
    results = dashboard.load_backtest_results()
    if not results:
        st.error("❌ No se pudieron cargar los resultados del backtesting")
        st.stop()

    # Calcular métricas resumen
    summary = dashboard.create_summary_metrics(results)

    # Verificar que summary no sea None
    if summary is None:
        st.error("Error: No se pudieron calcular las métricas resumen")
        return

    # Header principal
    st.markdown('<h1 class="main-header">📊 Bot Trader Copilot Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar-header">🎯 Panel de Control</div>', unsafe_allow_html=True)

        # Filtros
        selected_symbols = st.multiselect(
            "Seleccionar Símbolos",
            options=list(results.keys()),
            default=list(results.keys())  # Por defecto mostrar todos los símbolos
        )

        selected_strategies = st.multiselect(
            "Seleccionar Estrategias",
            options=list(set([strategy for symbol_data in results.values() for strategy in symbol_data.keys()])),
            default=list(set([strategy for symbol_data in results.values() for strategy in symbol_data.keys()]))
        )

        # Información del sistema
        st.markdown("### 📈 Información del Sistema")
        st.metric("Fecha de Análisis", datetime.now().strftime("%Y-%m-%d"))
        st.metric("Temporalidad", "15 Minutos")
        st.metric("Período", "2023-01-01 a 2025-06-01")

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Símbolos</div>
            <div class="metric-value">{summary['total_symbols']}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Símbolos Rentables</div>
            <div class="metric-value">{summary['profitable_symbols']}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        pnl_color = "green" if summary['total_pnl'] > 0 else "red"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">P&L Total</div>
            <div class="metric-value" style="color: {pnl_color}">${summary['total_pnl']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ratio Sharpe</div>
            <div class="metric-value">{summary.get('avg_sharpe_ratio', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # === MÉTRICAS AVANZADAS DE GESTIÓN DE RIESGO ===
    st.markdown("### 🛡️ Gestión de Riesgo Avanzada")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kelly_color = "green" if summary.get('avg_kelly_usage', 0) > 0 else "orange"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Uso Kelly Promedio</div>
            <div class="metric-value" style="color: {kelly_color}">{summary.get('avg_kelly_usage', 0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        corr_color = "green" if summary.get('avg_correlation_adjustment', 0) < 1.0 else "orange"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ajuste Correlación</div>
            <div class="metric-value" style="color: {corr_color}">{summary.get('avg_correlation_adjustment', 1.0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        vol_color = "green" if summary.get('avg_volatility_adjustment', 0) > 0 else "orange"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ajuste Volatilidad</div>
            <div class="metric-value" style="color: {vol_color}">{summary.get('avg_volatility_adjustment', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        risk_color = "green" if summary.get('avg_risk_score', 0) < 0.7 else "red"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Puntuación Riesgo</div>
            <div class="metric-value" style="color: {risk_color}">{summary.get('avg_risk_score', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # === MÉTRICAS DE COMPENSACIÓN ===
    st.markdown("### 🛡️ Sistema de Compensación")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        compensation_color = "green" if summary.get('total_compensated_trades', 0) > 0 else "orange"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Trades Compensados</div>
            <div class="metric-value" style="color: {compensation_color}">{summary.get('total_compensated_trades', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        comp_pnl_color = "green" if summary.get('total_compensation_pnl', 0) > 0 else "red"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">P&L Compensación</div>
            <div class="metric-value" style="color: {comp_pnl_color}">${summary.get('total_compensation_pnl', 0):,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Tasa Compensación</div>
            <div class="metric-value">{summary.get('avg_compensation_rate', 0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        adjusted_pnl = summary.get('adjusted_total_pnl', summary['total_pnl'])
        adjusted_color = "green" if adjusted_pnl > 0 else "red"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">P&L Ajustado</div>
            <div class="metric-value" style="color: {adjusted_color}">${adjusted_pnl:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Gráfico de P&L por símbolo
    st.markdown("### 📊 P&L por Símbolo")

    # Preparar datos para el gráfico
    chart_data = []
    for symbol in results.keys():  # Usar todos los símbolos disponibles
        if symbol in results:
            for strategy in results[symbol].keys():  # Usar todas las estrategias disponibles
                if strategy in results[symbol]:
                    result = results[symbol][strategy]
                    chart_data.append({
                        'Símbolo': symbol,
                        'Estrategia': strategy,
                        'P&L': result['total_pnl'],
                        'Win Rate': result['win_rate'],
                        'Trades': result['total_trades']
                    })

    if chart_data:
        df_chart = pd.DataFrame(chart_data)

        # Gráfico de barras P&L
        fig_pnl = px.bar(
            df_chart,
            x='Símbolo',
            y='P&L',
            color='Estrategia',
            title='P&L por Símbolo y Estrategia',
            barmode='group',
            height=500
        )
        fig_pnl.update_layout(
            xaxis_title="Símbolo",
            yaxis_title="P&L ($)",
            showlegend=True
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

        # Gráfico de Win Rate
        fig_winrate = px.scatter(
            df_chart,
            x='P&L',
            y='Win Rate',
            color='Símbolo',
            size='Trades',
            title='Relación P&L vs Win Rate',
            height=500
        )
        fig_winrate.update_layout(
            xaxis_title="P&L ($)",
            yaxis_title="Win Rate (%)",
            showlegend=True
        )
        st.plotly_chart(fig_winrate, use_container_width=True)

        # Gráfico de crecimiento de equity
        st.markdown("### 📈 Curva de Crecimiento de Capital")
        st.info("💡 La curva de equity se implementará cuando las estrategias generen datos de equity históricos durante el backtesting.")

    # Tabla detallada de resultados
    st.markdown("### 📋 Resultados Detallados")

    # Preparar datos para tabla
    table_data = []
    for symbol in results.keys():  # Usar todos los símbolos
        if symbol in results:
            best_strategy = max(results[symbol].items(), key=lambda x: x[1]['total_pnl'])
            strategy_name, result = best_strategy

            table_data.append({
                'Símbolo': symbol,
                'Mejor Estrategia': strategy_name,
                'P&L': f"${result['total_pnl']:,.0f}",
                'Win Rate': f"{result['win_rate'] * 100:.1f}%",  # ✅ CORREGIDO: Multiplicar por 100
                'Trades': result['total_trades'],
                'Max DD': f"{result['max_drawdown']:.1f}%",
                'Sharpe': f"{result['sharpe_ratio']:.2f}",
                # === COLUMNAS DE COMPENSACIÓN ===
                'Trades Perd.': result.get('losing_trades', 0),
                'Compensados': result.get('compensated_trades', 0),
                'Tasa Comp.': f"{result.get('compensation_success_rate', 0):.1f}%",
                'P&L Comp.': f"${result.get('total_compensation_pnl', 0):,.0f}",
                'P&L Ajustado': f"${result.get('adjusted_total_pnl', result['total_pnl']):,.0f}"
            })

    if table_data:
        df_table = pd.DataFrame(table_data)
        st.dataframe(df_table, use_container_width=True)

    # Ranking de mejores símbolos
    st.markdown("### 🏆 Ranking de Rendimiento")

    ranking_data = []
    for symbol in results.keys():
        best_strategy = max(results[symbol].items(), key=lambda x: x[1]['total_pnl'])
        strategy_name, result = best_strategy

        ranking_data.append({
            'Símbolo': symbol,
            'Estrategia': strategy_name,
            'P&L': result['total_pnl'],
            'Win Rate': result['win_rate'],
            'Sharpe': result.get('sharpe_ratio', 0),
            'Kelly %': result.get('avg_kelly_usage', 0),
            'Riesgo': result.get('avg_risk_score', 0),
            # === MÉTRICAS DE COMPENSACIÓN ===
            'Compensados': result.get('compensated_trades', 0),
            'P&L Comp.': result.get('total_compensation_pnl', 0),
            'P&L Ajustado': result.get('adjusted_total_pnl', result['total_pnl'])
        })

    ranking_df = pd.DataFrame(ranking_data).sort_values('P&L Ajustado', ascending=False).reset_index(drop=True)

    # Mostrar ranking con formato mejorado
    st.markdown("#### 🥇🥈🥉 Top 10 Símbolos por Rentabilidad")
    for i, row in ranking_df.head(10).iterrows():
        if i == 0:
            medal = "🥇"
            medal_text = "ORO"
        elif i == 1:
            medal = "🥈"
            medal_text = "PLATA"
        elif i == 2:
            medal = "🥉"
            medal_text = "BRONCE"
        else:
            medal = f"#{i+1}"
            medal_text = f"Posición {i+1}"

        pnl_color = "green" if row['P&L Ajustado'] > 0 else "red"

        st.markdown(f"""
        <div style="display: flex; align-items: center; padding: 1rem; border-radius: 10px; background: linear-gradient(135deg, {'#FFD700' if i == 0 else '#C0C0C0' if i == 1 else '#CD7F32' if i == 2 else '#f0f0f0'} 0%, rgba(255,255,255,0.9) 100%); margin: 0.5rem 0; border: 2px solid {'#FFD700' if i == 0 else '#C0C0C0' if i == 1 else '#CD7F32' if i == 2 else '#ddd'}; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="font-size: 2rem; margin-right: 1rem;">{medal}</div>
            <div style="flex: 1;">
                <div style="font-weight: bold; font-size: 1.2rem; color: #333;">{row['Símbolo']}</div>
                <div style="color: #666; font-size: 0.9rem;">{row['Estrategia']} • WR: {row['Win Rate']:.1f}% • Sharpe: {row['Sharpe']:.2f}</div>
                <div style="color: #888; font-size: 0.8rem;">Kelly: {row['Kelly %']:.1f}% • Riesgo: {row['Riesgo']:.2f}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-weight: bold; font-size: 1.4rem; color: {pnl_color};">${row['P&L Ajustado']:,.0f}</div>
                <div style="color: #4CAF50; font-size: 0.9rem;">+${row['P&L Comp.']:,.0f} comp.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        <strong>Bot Trader Copilot v1.0</strong> - Dashboard Profesional de Backtesting<br>
        Desarrollado con ❤️ para análisis avanzado de trading
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    # Auto-lanzamiento del dashboard
    import subprocess
    import sys
    import os

    print("LANZANDO DASHBOARD PROFESIONAL...")
    print("=" * 50)

    # Verificar que los datos existen
    data_path = Path(r"c:\Users\javie\proyecto bot copilot\bot trader copilot version 1.0\descarga_datos\data\dashboard_results")

    if not data_path.exists():
        print(f"Datos no encontrados: {data_path}")
        print("Ejecuta el backtesting primero para generar los datos")
        sys.exit(1)

    json_files = list(data_path.glob("*.json"))
    print(f"Datos encontrados: {len(json_files)} archivos JSON")

    # Cambiar al directorio del dashboard para ejecución correcta
    dashboard_dir = Path(__file__).parent
    os.chdir(dashboard_dir)

    print(f"Ejecutando desde: {dashboard_dir}")

    try:
        # Ejecutar el dashboard
        print("Iniciando dashboard...")
        print("Dashboard disponible en: http://localhost:8501")
        print("\nEl dashboard se esta cargando...")
        print("   - Verifica que las rutas de datos esten corregidas")
        print("   - Las graficas de equity deberian aparecer automaticamente")
        print("   - Las metricas de compensacion estaran completas")
        print("   - Las metricas avanzadas de riesgo estaran disponibles")

        # Ejecutar streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__], check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando dashboard: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDashboard detenido por el usuario")
        sys.exit(0)
