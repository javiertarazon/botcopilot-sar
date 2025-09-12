#!/usr/bin/env python3
"""
Dashboard Module - Bot Trader Copilot
=====================================

Módulo de visualización y análisis de resultados de backtesting.
Proporciona interfaces web profesionales para el análisis de estrategias de trading.
"""

__version__ = "1.0.0"
__author__ = "Bot Trader Copilot"
__description__ = "Dashboard profesional para análisis de backtesting y gestión de riesgo"

# Funciones de utilidad para el módulo dashboard
def get_dashboard_info():
    """Obtiene información sobre el módulo dashboard"""
    return {
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "features": [
            "Dashboard web profesional con Streamlit",
            "Visualización de métricas de backtesting",
            "Sistema de compensación integrado",
            "Análisis avanzado de gestión de riesgo",
            "Métricas de Kelly Criterion",
            "Análisis de correlaciones",
            "Ranking de rendimiento por símbolo",
            "Auto-lanzamiento del dashboard"
        ]
    }

def check_data_availability():
    """Verifica la disponibilidad de datos para el dashboard"""
    import os
    from pathlib import Path

    # Posibles ubicaciones de datos
    data_paths = [
        Path("../../data/dashboard_results"),
        Path("../data/dashboard_results"),
        Path("./data/dashboard_results"),
        Path("data/dashboard_results")
    ]

    for path in data_paths:
        if path.exists():
            json_files = list(path.glob("*.json"))
            return {
                "available": True,
                "path": str(path),
                "json_files_count": len(json_files),
                "json_files": [f.name for f in json_files]
            }

    return {
        "available": False,
        "message": "No se encontraron datos de backtesting. Ejecuta el backtesting primero."
    }

# Información de inicialización
print("📊 Dashboard Module Initialized")
print(f"   Version: {__version__}")
print(f"   Author: {__author__}")
print("   Ready for backtesting analysis!")
