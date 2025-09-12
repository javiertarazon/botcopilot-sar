#!/usr/bin/env python3
"""
Script de Optimización Específica para TSLA
Prueba múltiples combinaciones de parámetros para maximizar rentabilidad
"""

import pandas as pd
import numpy as np
import os
import itertools
from strategies.ut_bot_basico_con_modulo_gestion_riesgo import UTBotBasicoConModuloGestionRiesgo
import json
from datetime import datetime

def load_tsla_data(timeframe="15m"):
    """Carga datos históricos de TSLA"""
    symbol_map = {
        "TSLA": "TSLA_US"
    }

    base_name = symbol_map.get("TSLA", "TSLA")
    filename = f"{base_name}_{timeframe}.csv"
    filepath = os.path.join("data", "csv", filename)

    if not os.path.exists(filepath):
        print(f"❌ Archivo no encontrado: {filepath}")
        return None

    try:
        df = pd.read_csv(filepath)

        # Renombrar columnas si es necesario
        column_mapping = {
            'timestamp': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }

        df = df.rename(columns=column_mapping)

        # Convertir timestamp si es necesario
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        # Asegurar tipos de datos numéricos
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Calcular indicadores técnicos faltantes
        if 'ema_10' not in df.columns:
            df['ema_10'] = df['close'].ewm(span=10).mean()
        if 'ema_20' not in df.columns:
            df['ema_20'] = df['close'].ewm(span=20).mean()
        if 'ema_200' not in df.columns:
            df['ema_200'] = df['close'].ewm(span=200).mean()

        # Calcular ATR si no existe
        if 'atr' not in df.columns:
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = true_range.rolling(window=14).mean()

        # Calcular PSAR si no existe
        if 'sar' not in df.columns:
            df['sar'] = df['low'].shift(1)

        print(f"✅ Datos cargados: {len(df)} velas de TSLA")
        return df

    except Exception as e:
        print(f"❌ Error cargando datos de TSLA: {e}")
        return None

def optimize_tsla_parameters():
    """Optimiza parámetros para TSLA probando múltiples combinaciones"""

    print("🚀 OPTIMIZACIÓN DE PARÁMETROS PARA TSLA")
    print("=" * 60)
    print("🎯 Objetivo: Maximizar rentabilidad probando diferentes combinaciones")
    print()

    # Cargar datos de TSLA
    df = load_tsla_data("15m")
    if df is None or len(df) < 200:
        print("❌ No se pudieron cargar datos suficientes de TSLA")
        return

    print(f"💰 Precio inicial: ${df['close'].iloc[0]:.2f}")
    print(f"💰 Precio final: ${df['close'].iloc[-1]:.2f}")
    retorno_mercado = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
    print(f"📈 Retorno total del mercado: {retorno_mercado:.1f}%")
    print()

    # Definir rangos de parámetros para optimización
    param_ranges = {
        'sensitivity': [1.0, 1.2, 1.5, 1.8, 2.0, 2.5],  # Sensibilidad del algoritmo
        'risk_percent': [1.0, 1.5, 2.0, 2.5, 3.0],       # Porcentaje de riesgo por trade
        'tp_atr_multiplier': [2.0, 2.5, 3.0, 3.5, 4.0],  # Multiplicador para take profit
        'sl_atr_multiplier': [1.0, 1.2, 1.5, 1.8, 2.0]   # Multiplicador para stop loss
    }

    print("🔧 RANGOS DE PARÁMETROS A PROBAR:")
    for param, values in param_ranges.items():
        print(f"  {param}: {values}")
    print()

    # Calcular total de combinaciones
    total_combinations = 1
    for values in param_ranges.values():
        total_combinations *= len(values)

    print(f"📊 Total de combinaciones a probar: {total_combinations}")
    print("⏱️ Esto puede tomar varios minutos...")
    print()

    # Lista para almacenar resultados
    optimization_results = []

    # Generar todas las combinaciones de parámetros
    param_combinations = list(itertools.product(*param_ranges.values()))
    param_names = list(param_ranges.keys())

    best_result = None
    best_return = -1000
    best_sharpe = -1000

    print("🔄 INICIANDO OPTIMIZACIÓN...")
    print("-" * 60)
    print(f"⏰ Inicio: {datetime.now().strftime('%H:%M:%S')}")
    print()

    start_time = datetime.now()
    last_progress_time = start_time

    for i, params in enumerate(param_combinations):
        param_dict = dict(zip(param_names, params))

        # Log detallado del progreso
        current_time = datetime.now()
        elapsed_time = current_time - start_time
        combinations_completed = i
        combinations_remaining = total_combinations - combinations_completed - 1
        progress_percent = (combinations_completed / total_combinations) * 100

        # Mostrar progreso cada 5 combinaciones o cada 30 segundos
        if (i + 1) % 5 == 0 or (current_time - last_progress_time).seconds >= 30:
            print(f"🔄 [{current_time.strftime('%H:%M:%S')}] Progreso: {combinations_completed + 1}/{total_combinations} ({progress_percent:.1f}%)")
            print(f"   ⏱️ Tiempo transcurrido: {elapsed_time}")
            print(f"   📊 Combinaciones restantes: {combinations_remaining}")
            print(f"   🎯 Mejor retorno actual: {best_return:.2f}%")
            print(f"   ⚙️ Parámetros actuales: {param_dict}")
            print()
            last_progress_time = current_time

        try:
            # Crear estrategia con parámetros actuales
            estrategia = UTBotBasicoConModuloGestionRiesgo(
                sensitivity=param_dict['sensitivity'],
                atr_period=14,
                risk_percent=param_dict['risk_percent'],
                tp_atr_multiplier=param_dict['tp_atr_multiplier'],
                sl_atr_multiplier=param_dict['sl_atr_multiplier']
            )

            # Ejecutar backtest
            resultados = estrategia.run(df, "TSLA")

            # Calcular métricas adicionales
            total_return = resultados.get('total_return', 0)
            sharpe_ratio = resultados.get('sharpe_ratio', -100)
            max_drawdown = resultados.get('max_drawdown_percent', 100)
            win_rate = resultados.get('win_rate', 0)
            total_trades = resultados.get('total_trades', 0)

            # Solo considerar resultados con al menos 10 trades
            if total_trades >= 10:
                result_entry = {
                    'combination_id': i + 1,
                    'parameters': param_dict,
                    'metrics': {
                        'total_return': total_return,
                        'sharpe_ratio': sharpe_ratio,
                        'max_drawdown': max_drawdown,
                        'win_rate': win_rate,
                        'total_trades': total_trades,
                        'total_pnl': resultados.get('total_pnl', 0)
                    }
                }

                optimization_results.append(result_entry)

                # Actualizar mejor resultado
                if total_return > best_return:
                    best_return = total_return
                    best_result = result_entry
                    print(f"🎯 ¡NUEVO MEJOR RESULTADO! Retorno: {best_return:.2f}% (Combinación {i + 1})")

                # Log de cada combinación exitosa
                print(f"✅ Combinación {i + 1} completada - Retorno: {total_return:.2f}%, Trades: {total_trades}")

        except Exception as e:
            print(f"❌ Error en combinación {i + 1}: {e}")
            continue

        except Exception as e:
            print(f"❌ Error en combinación {i + 1}: {e}")
            continue

    print("\n🎯 OPTIMIZACIÓN COMPLETADA")
    print("=" * 60)

    end_time = datetime.now()
    total_elapsed = end_time - start_time
    print(f"⏰ Tiempo total de optimización: {total_elapsed}")
    print(f"📊 Combinaciones procesadas: {len(optimization_results)}/{total_combinations}")
    print(f"📈 Rendimiento: {len(optimization_results)/total_elapsed.total_seconds():.2f} combinaciones/segundo")
    print()

    if not optimization_results:
        print("❌ No se obtuvieron resultados válidos")
        return

    # Ordenar resultados por retorno total
    optimization_results.sort(key=lambda x: x['metrics']['total_return'], reverse=True)

    print("🏆 TOP 10 MEJORES CONFIGURACIONES:")
    print("-" * 100)
    print("<12")
    print("-" * 100)

    for i, result in enumerate(optimization_results[:10], 1):
        params = result['parameters']
        metrics = result['metrics']

        print("2d"
              "6.2f"
              "5.1f"
              "5.1f"
              "3d")

    print()
    print("🎯 MEJOR CONFIGURACIÓN ENCONTRADA:")
    print("-" * 50)

    if best_result:
        best_params = best_result['parameters']
        best_metrics = best_result['metrics']

        print("⚙️ PARÁMETROS ÓPTIMOS:")
        print(f"  Sensitivity: {best_params['sensitivity']}")
        print(f"  Risk %: {best_params['risk_percent']}%")
        print(f"  TP Multiplier: {best_params['tp_atr_multiplier']}")
        print(f"  SL Multiplier: {best_params['sl_atr_multiplier']}")
        print()
        print("📊 MÉTRICAS:")
        print(f"  Retorno Total: {best_metrics['total_return']:.2f}%")
        print(f"  Sharpe Ratio: {best_metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {best_metrics['max_drawdown']:.1f}%")
        print(f"  Win Rate: {best_metrics['win_rate']:.1f}%")
        print(f"  Total Trades: {best_metrics['total_trades']}")

    # Guardar resultados en archivo JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"tsla_optimization_results_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'optimization_summary': {
                'symbol': 'TSLA',
                'total_combinations_tested': len(optimization_results),
                'market_return': retorno_mercado,
                'best_result': best_result,
                'timestamp': datetime.now().isoformat()
            },
            'top_10_results': optimization_results[:10],
            'all_results': optimization_results
        }, f, indent=2, default=str)

    print(f"\n💾 Resultados guardados en: {output_file}")

    # Análisis estadístico
    print("\n📈 ANÁLISIS ESTADÍSTICO:")
    print("-" * 40)

    returns = [r['metrics']['total_return'] for r in optimization_results]
    win_rates = [r['metrics']['win_rate'] for r in optimization_results]
    sharpe_ratios = [r['metrics']['sharpe_ratio'] for r in optimization_results]

    print(f"📊 Retorno promedio: {sum(returns)/len(returns):.2f}%")
    print(f"📈 Mejor retorno: {max(returns):.2f}%")
    print(f"📉 Peor retorno: {min(returns):.2f}%")
    print(f"🎯 Win Rate promedio: {sum(win_rates)/len(win_rates):.1f}%")
    print(f"📊 Sharpe Ratio promedio: {sum(sharpe_ratios)/len(sharpe_ratios):.2f}")
    print(f"💎 Mejor Sharpe: {max(sharpe_ratios):.2f}")
    print(f"📉 Peor Sharpe: {min(sharpe_ratios):.2f}")

    # Comparación con mercado
    profitable_configs = sum(1 for r in optimization_results if r['metrics']['total_return'] > retorno_mercado)
    print(f"🏆 Configuraciones que superan el mercado: {profitable_configs}/{len(optimization_results)} ({profitable_configs/len(optimization_results)*100:.1f}%)")

    print("\n✅ OPTIMIZACIÓN FINALIZADA CON ÉXITO")
    return best_result

if __name__ == "__main__":
    optimize_tsla_parameters()