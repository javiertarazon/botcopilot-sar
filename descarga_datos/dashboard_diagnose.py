#!/usr/bin/env python3
"""
Script de diagnóstico para el dashboard
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any

def diagnose_dashboard():
    """Diagnostica problemas en el dashboard"""

    print("🔍 DIAGNÓSTICO DEL DASHBOARD")
    print("=" * 50)

    # Verificar rutas
    results_dir = Path(r"c:\Users\javie\proyecto bot copilot\bot trader copilot version 1.0\descarga_datos\data\dashboard_results")

    if not results_dir.exists():
        print("❌ Directorio de resultados no existe")
        return

    print(f"✅ Directorio encontrado: {results_dir}")

    # Verificar archivos
    json_files = list(results_dir.glob("*.json"))
    print(f"📁 Archivos JSON encontrados: {len(json_files)}")

    for json_file in json_files[:3]:  # Revisar primeros 3
        print(f"\n📄 Analizando: {json_file.name}")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'strategies' in data:
                strategies = list(data['strategies'].keys())
                print(f"   📊 Estrategias encontradas: {strategies}")

                for strategy_name, strategy_data in data['strategies'].items():
                    required_fields = ['total_pnl', 'total_trades', 'win_rate']
                    missing_fields = [field for field in required_fields if field not in strategy_data]
                    if missing_fields:
                        print(f"   ⚠️  Campos faltantes en {strategy_name}: {missing_fields}")
                    else:
                        pnl = strategy_data.get('total_pnl', 0)
                        trades = strategy_data.get('total_trades', 0)
                        print(f"   ✅ {strategy_name}: P&L=${pnl:,.2f}, Trades={trades}")
            else:
                print("   ⚠️  No se encontraron estrategias en el archivo")

        except Exception as e:
            print(f"   ❌ Error leyendo archivo: {e}")

    # Verificar estructura esperada por el dashboard
    print("\n🔧 VERIFICACIÓN DE ESTRUCTURA PARA DASHBOARD")
    print("-" * 50)

    global_summary = results_dir / "global_summary.json"
    if global_summary.exists():
        try:
            with open(global_summary, 'r', encoding='utf-8') as f:
                global_data = json.load(f)

            print("✅ Archivo global_summary.json encontrado")

            # Verificar métricas principales
            metrics = global_data.get('metrics', {})
            required_metrics = ['total_pnl', 'total_trades', 'profitable_symbols', 'avg_win_rate']

            for metric in required_metrics:
                if metric in metrics:
                    print(f"✅ Métrica {metric}: {metrics[metric]}")
                else:
                    print(f"❌ Métrica faltante: {metric}")

        except Exception as e:
            print(f"❌ Error leyendo global_summary.json: {e}")
    else:
        print("❌ global_summary.json no encontrado")

    # Verificar archivos individuales
    symbol_files = [f for f in results_dir.glob("*_results.json") if f.name != "global_summary.json"]
    print(f"\n📊 Archivos de símbolos: {len(symbol_files)}")

    if symbol_files:
        sample_file = symbol_files[0]
        try:
            with open(sample_file, 'r', encoding='utf-8') as f:
                sample_data = json.load(f)

            print(f"✅ Estructura de {sample_file.name}:")
            print(f"   - Symbol: {sample_data.get('symbol', 'N/A')}")
            print(f"   - Timestamp: {sample_data.get('timestamp', 'N/A')}")
            print(f"   - Strategies: {list(sample_data.get('strategies', {}).keys())}")

        except Exception as e:
            print(f"❌ Error leyendo archivo de ejemplo: {e}")

    print("\n🎯 RECOMENDACIONES")
    print("-" * 30)

    if len(json_files) == 0:
        print("❌ No hay archivos JSON. Ejecuta el backtesting primero.")
    elif not global_summary.exists():
        print("⚠️  Falta global_summary.json")
    else:
        print("✅ Estructura básica correcta")
        print("💡 Si el dashboard no muestra datos, verifica:")
        print("   - Que las rutas en el dashboard estén correctas")
        print("   - Que los nombres de estrategias coincidan")
        print("   - Que las métricas requeridas estén presentes")

if __name__ == "__main__":
    diagnose_dashboard()
