#!/usr/bin/env python3
"""
Comparación de Temporalidades para TSLA
Prueba la estrategia con diferentes timeframes: 5m, 15m, 1h, 4h
"""

import pandas as pd
import numpy as np
import os
from strategies.ut_bot_basico_con_modulo_gestion_riesgo import UTBotBasicoConModuloGestionRiesgo
import json
from datetime import datetime

def generate_5m_data_from_15m(df_15m):
    """Convierte datos de 15 minutos a 5 minutos usando interpolación realista"""
    if df_15m is None or len(df_15m) < 2:
        return None

    print("🔄 Convirtiendo datos de 15m a 5m usando interpolación...")

    # Crear nuevo DataFrame con 3 veces más filas (cada 15 min -> 3 velas de 5 min)
    data_5m = []

    for i in range(len(df_15m) - 1):
        current_row = df_15m.iloc[i]
        next_row = df_15m.iloc[i + 1]

        # Timestamp base
        if hasattr(current_row.name, 'timestamp'):
            base_time = current_row.name
        else:
            base_time = pd.Timestamp.now() - pd.Timedelta(minutes=15 * (len(df_15m) - i))

        # Usar interpolación más realista basada en el movimiento del precio
        # Calcular la dirección y volatilidad del período de 15 minutos
        price_change = current_row['close'] - current_row['open']
        volatility = (current_row['high'] - current_row['low']) / current_row['open']

        # Generar 3 velas de 5 minutos con movimiento más natural
        for j in range(3):
            # Progresión natural del precio dentro del período de 15 minutos
            progress = (j + 1) / 3  # 0.33, 0.67, 1.0

            if j == 0:  # Primera vela de 5 min
                open_price = current_row['open']
                # Primer tercio del movimiento
                target_change = price_change * 0.3
                close_price = open_price + target_change
                # Ajustar high/low basado en volatilidad
                high_price = max(open_price, close_price) * (1 + volatility * 0.3)
                low_price = min(open_price, close_price) * (1 - volatility * 0.3)

            elif j == 1:  # Segunda vela de 5 min
                open_price = close_price
                # Segundo tercio del movimiento
                remaining_change = price_change * 0.7 - (close_price - current_row['open'])
                close_price = open_price + remaining_change
                # High/low con menor volatilidad
                high_price = max(open_price, close_price) * (1 + volatility * 0.2)
                low_price = min(open_price, close_price) * (1 - volatility * 0.2)

            else:  # Tercera vela de 5 min
                open_price = close_price
                # Último tercio para llegar al precio de cierre real
                close_price = current_row['close']
                # High/low basado en el movimiento final
                high_price = max(open_price, close_price, current_row['high'])
                low_price = min(open_price, close_price, current_row['low'])

            # Asegurar que los precios estén dentro de los límites reales
            high_price = min(high_price, current_row['high'])
            low_price = max(low_price, current_row['low'])

            # Crear timestamp para cada vela de 5 min
            vela_time = base_time + pd.Timedelta(minutes=5 * j)

            data_5m.append({
                'timestamp': vela_time,
                'open': round(open_price, 4),
                'high': round(high_price, 4),
                'low': round(low_price, 4),
                'close': round(close_price, 4),
                'volume': int(current_row['volume'] / 3)  # Distribuir volumen
            })

    # Crear DataFrame
    df_5m = pd.DataFrame(data_5m)
    df_5m['timestamp'] = pd.to_datetime(df_5m['timestamp'])
    df_5m.set_index('timestamp', inplace=True)

    # Calcular indicadores técnicos
    df_5m['ema_10'] = df_5m['close'].ewm(span=10).mean()
    df_5m['ema_20'] = df_5m['close'].ewm(span=20).mean()
    df_5m['ema_200'] = df_5m['close'].ewm(span=200).mean()

    # Calcular ATR
    high_low = df_5m['high'] - df_5m['low']
    high_close = abs(df_5m['high'] - df_5m['close'].shift(1))
    low_close = abs(df_5m['low'] - df_5m['close'].shift(1))
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_5m['atr'] = true_range.rolling(window=14).mean()

    # Calcular PSAR
    df_5m['sar'] = df_5m['low'].shift(1)

    print(f"✅ Conversión completada: {len(df_5m)} velas de 5m generadas")
    return df_5m

def load_tsla_data(timeframe="15m"):
    """Carga datos históricos de TSLA para diferentes temporalidades"""
    symbol_map = {
        "TSLA": "TSLA_US"
    }

    base_name = symbol_map.get("TSLA", "TSLA")
    filename = f"{base_name}_{timeframe}.csv"
    filepath = os.path.join("data", "csv", filename)

    # Si es 5m y no existe el archivo, convertir desde 15m
    if timeframe == "5m" and not os.path.exists(filepath):
        print("� Convirtiendo datos históricos de 15m a 5m...")
        df_15m = load_tsla_data("15m")
        if df_15m is not None:
            df = generate_5m_data_from_15m(df_15m)
            if df is not None:
                print(f"✅ Datos convertidos: {len(df)} velas de TSLA (5m)")
                return df
        return None

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

        print(f"✅ Datos cargados: {len(df)} velas de TSLA ({timeframe})")
        return df

    except Exception as e:
        print(f"❌ Error cargando datos de TSLA ({timeframe}): {e}")
        return None

def test_timeframe(timeframe, best_params):
    """Prueba la estrategia con un timeframe específico"""
    print(f"\n🔄 PROBANDO TIMEFRAME: {timeframe}")
    print("-" * 50)

    # Cargar datos
    df = load_tsla_data(timeframe)
    if df is None or len(df) < 200:
        print(f"❌ No se pudieron cargar datos suficientes para {timeframe}")
        return None

    print(f"💰 Precio inicial: ${df['close'].iloc[0]:.2f}")
    print(f"💰 Precio final: ${df['close'].iloc[-1]:.2f}")
    retorno_mercado = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
    print(f"📈 Retorno total del mercado: {retorno_mercado:.1f}%")

    try:
        # Crear estrategia con mejores parámetros encontrados
        estrategia = UTBotBasicoConModuloGestionRiesgo(
            sensitivity=best_params['sensitivity'],
            atr_period=14,
            risk_percent=best_params['risk_percent'],
            tp_atr_multiplier=best_params['tp_atr_multiplier'],
            sl_atr_multiplier=best_params['sl_atr_multiplier']
        )

        print(f"⚙️ Parámetros utilizados: {best_params}")

        # Ejecutar backtest
        start_time = datetime.now()
        resultados = estrategia.run(df, "TSLA")
        end_time = datetime.now()

        tiempo_ejecucion = end_time - start_time
        print(f"⏱️ Tiempo de ejecución: {tiempo_ejecucion}")

        # Extraer métricas
        total_return = resultados.get('total_return', 0)
        sharpe_ratio = resultados.get('sharpe_ratio', 0)
        max_drawdown = resultados.get('max_drawdown_percent', 0)
        win_rate = resultados.get('win_rate', 0)
        total_trades = resultados.get('total_trades', 0)
        total_pnl = resultados.get('total_pnl', 0)

        print("\n📊 RESULTADOS:")
        print(f"  Retorno Total: {total_return:.2f}%")
        print(f"  Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"  Max Drawdown: {max_drawdown:.1f}%")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total Trades: {total_trades}")
        print(f"  P&L Total: ${total_pnl:.2f}")

        # Comparación con mercado
        vs_mercado = total_return - retorno_mercado
        print(f"  VS Mercado: {vs_mercado:+.2f}%")

        return {
            'timeframe': timeframe,
            'market_return': retorno_mercado,
            'strategy_return': total_return,
            'vs_market': vs_mercado,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'execution_time': tiempo_ejecucion.total_seconds(),
            'data_points': len(df)
        }

    except Exception as e:
        print(f"❌ Error ejecutando estrategia para {timeframe}: {e}")
        return None

def compare_timeframes():
    """Compara la estrategia en diferentes temporalidades"""

    print("🚀 COMPARACIÓN DE TEMPORALIDADES PARA TSLA")
    print("=" * 70)
    print("🎯 Probando estrategia con mejores parámetros encontrados")
    print("📊 Timeframes: 5m, 15m, 1h, 4h")
    print()

    # Mejores parámetros de la optimización anterior
    best_params = {
        'sensitivity': 1.0,
        'risk_percent': 2.5,
        'tp_atr_multiplier': 2.5,
        'sl_atr_multiplier': 1.0
    }

    print("⚙️ PARÁMETROS ÓPTIMOS UTILIZADOS:")
    print(f"  Sensitivity: {best_params['sensitivity']}")
    print(f"  Risk %: {best_params['risk_percent']}%")
    print(f"  TP Multiplier: {best_params['tp_atr_multiplier']}")
    print(f"  SL Multiplier: {best_params['sl_atr_multiplier']}")
    print()

    # Timeframes a probar
    timeframes = ['5m', '15m', '1h', '4h']
    results = []

    # Probar cada timeframe
    for timeframe in timeframes:
        result = test_timeframe(timeframe, best_params)
        if result:
            results.append(result)

    if not results:
        print("❌ No se pudieron obtener resultados para ningún timeframe")
        return

    print("\n" + "=" * 70)
    print("🏆 RESUMEN COMPARATIVO")
    print("=" * 70)

    # Crear tabla comparativa
    print(f"{'Timeframe':<12} {'Mercado':<10} {'Estrategia':<12} {'VS Mercado':<12} {'Win Rate':<10} {'Trades':<8} {'Drawdown':<10}")
    print("-" * 90)

    for result in results:
        print(f"{result['timeframe']:<12} {result['market_return']:<10.1f} {result['strategy_return']:<12.2f} {result['vs_market']:<12.2f} {result['win_rate']:<10.1f} {result['total_trades']:<8} {result['max_drawdown']:<10.1f}")

    print()

    # Análisis detallado
    print("📈 ANÁLISIS DETALLADO:")
    print("-" * 40)

    # Encontrar mejor timeframe
    best_result = max(results, key=lambda x: x['strategy_return'])

    print(f"🎯 Mejor Timeframe: {best_result['timeframe']}")
    print(f"  Retorno: {best_result['strategy_return']:.2f}%")
    print(f"  VS Mercado: {best_result['vs_market']:+.2f}%")
    print(f"  Win Rate: {best_result['win_rate']:.1f}%")
    print(f"  Total Trades: {best_result['total_trades']}")
    print()

    # Análisis por timeframe
    for result in results:
        timeframe = result['timeframe']
        analysis = []

        if result['strategy_return'] > result['market_return']:
            analysis.append("✅ Supera al mercado")
        else:
            analysis.append("❌ Por debajo del mercado")

        if result['win_rate'] > 0.4:
            analysis.append("✅ Win Rate bueno (>40%)")
        elif result['win_rate'] > 0.3:
            analysis.append("🟡 Win Rate aceptable (30-40%)")
        else:
            analysis.append("❌ Win Rate bajo (<30%)")

        if result['max_drawdown'] < 10:
            analysis.append("✅ Drawdown bajo (<10%)")
        elif result['max_drawdown'] < 20:
            analysis.append("🟡 Drawdown moderado (10-20%)")
        else:
            analysis.append("❌ Drawdown alto (>20%)")

        print(f"📊 {timeframe}:")
        for item in analysis:
            print(f"  {item}")
        print()

    # Guardar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"timeframe_comparison_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'comparison_summary': {
                'best_params': best_params,
                'timeframes_tested': timeframes,
                'best_timeframe': best_result['timeframe'],
                'timestamp': datetime.now().isoformat()
            },
            'results': results
        }, f, indent=2, default=str)

    print(f"💾 Resultados guardados en: {output_file}")

    # Recomendaciones finales
    print("\n🎯 RECOMENDACIONES:")
    print("-" * 30)

    if best_result['strategy_return'] > 0:
        print(f"✅ Recomendado: {best_result['timeframe']} (mejor retorno positivo)")
    else:
        best_positive = [r for r in results if r['strategy_return'] > 0]
        if best_positive:
            best_pos = max(best_positive, key=lambda x: x['strategy_return'])
            print(f"✅ Recomendado: {best_pos['timeframe']} (único con retorno positivo)")
        else:
            print("⚠️ Ningún timeframe genera retorno positivo")

    print(f"📊 Total timeframes probados: {len(results)}")
    print(f"⏱️ Tiempo total de comparación: {sum(r['execution_time'] for r in results):.1f} segundos")

    print("\n✅ COMPARACIÓN FINALIZADA CON ÉXITO")
    return results

if __name__ == "__main__":
    compare_timeframes()