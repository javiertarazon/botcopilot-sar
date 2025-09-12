"""
SCRIPT DE COMPARACIÓN DE ESTRATEGIAS
====================================

Compara todas las estrategias disponibles y genera un reporte completo
de rendimiento, riesgos y características.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import os

# Importar estrategias existentes
try:
    from strategies.ut_bot_psar import UTBotPSARStrategy
    from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy
    from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy
    from strategies.advanced_ut_bot_strategy import AdvancedUTBotStrategy
    from strategies.optimized_strategy import UTBotPSAROptimized
    from strategies.unified_ut_bot_strategy import UnifiedStrategyConfig
    from strategies.ml_adaptive_strategy import MLAdaptiveUTBotStrategy, AdaptiveStrategyConfig
    from strategies.multitimeframe_sentiment_strategy import SentimentMultiTimeframeStrategy
    from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy, StatisticalArbitrageConfig
    from strategies.momentum_volume_strategy import MomentumVolumeStrategy, MomentumVolumeConfig
except ImportError:
    # Si hay problemas con importaciones relativas, intentar importaciones absolutas
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))

    from strategies.ut_bot_psar import UTBotPSARStrategy
    from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy
    from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy
    from strategies.advanced_ut_bot_strategy import AdvancedUTBotStrategy
    from strategies.optimized_strategy import UTBotPSAROptimized
    from strategies.unified_ut_bot_strategy import UnifiedStrategyConfig
    from strategies.ml_adaptive_strategy import MLAdaptiveUTBotStrategy, AdaptiveStrategyConfig
    from strategies.multitimeframe_sentiment_strategy import SentimentMultiTimeframeStrategy
    from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy, StatisticalArbitrageConfig
    from strategies.momentum_volume_strategy import MomentumVolumeStrategy, MomentumVolumeConfig

class StrategyComparator:
    """
    Compara múltiples estrategias de trading y genera reportes detallados
    """

    def __init__(self):
        self.strategies = {}
        self.results = {}
        self.comparison_metrics = {}

    def add_strategy(self, name: str, strategy_class, config=None):
        """Agrega una estrategia para comparación"""
        self.strategies[name] = {
            'class': strategy_class,
            'config': config,
            'results': None
        }

    def load_real_data(self, symbol: str = "BTC/USDT") -> pd.DataFrame:
        """
        Carga datos históricos reales desde archivos CSV existentes
        """
        try:
            print(f"   📥 Cargando datos históricos reales para {symbol}...")
            
            # Mapear símbolo al archivo CSV
            symbol_mapping = {
                "BTC/USDT": "BTC_USDT_1h.csv",
                "ETH/USDT": "ETH_USDT_1h.csv",
                "AAPL": "AAPL_US_1h.csv",
                "TSLA": "TSLA_US_1h.csv"
            }
            
            if symbol not in symbol_mapping:
                print(f"   ⚠️ Símbolo {symbol} no tiene archivo de datos, usando sintético")
                return self._generate_synthetic_data(symbol)
            
            csv_filename = symbol_mapping[symbol]
            csv_path = f"data/csv/{csv_filename}"
            
            if not os.path.exists(csv_path):
                print(f"   ⚠️ Archivo {csv_path} no existe, usando datos sintéticos")
                return self._generate_synthetic_data(symbol)
            
            # Cargar datos desde CSV
            df = pd.read_csv(csv_path)
            
            # Convertir timestamp a datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Validar que tenemos datos suficientes
            if len(df) < 200:
                print(f"   ⚠️ Datos insuficientes en {csv_path} ({len(df)} filas), usando sintético")
                return self._generate_synthetic_data(symbol)
            
            print(f"   ✅ Cargados {len(df)} registros históricos reales para {symbol}")
            
            # Agregar indicadores técnicos si no existen
            if 'ema_10' not in df.columns:
                df = self._add_technical_indicators(df)
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error cargando datos reales para {symbol}: {e}")
            print(f"   🔄 Usando datos sintéticos como fallback")
            return self._generate_synthetic_data(symbol)

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega indicadores técnicos necesarios para las estrategias"""
        data = df.copy()
        
        # Indicadores básicos
        data['ema_10'] = data['close'].ewm(span=10).mean()
        data['ema_20'] = data['close'].ewm(span=20).mean()
        data['ema_200'] = data['close'].ewm(span=200).mean()
        
        # ATR
        high = data['high']
        low = data['low']
        close = data['close']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['atr'] = tr.rolling(window=14).mean()
        
        # PSAR
        data['sar'] = self._calculate_psar(data)
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = data['close'].ewm(span=12).mean()
        ema_26 = data['close'].ewm(span=26).mean()
        data['macd'] = ema_12 - ema_26
        data['macd_signal'] = data['macd'].ewm(span=9).mean()
        data['macd_hist'] = data['macd'] - data['macd_signal']
        
        # Bollinger Bands
        sma_20 = data['close'].rolling(window=20).mean()
        std_20 = data['close'].rolling(window=20).std()
        data['bb_upper'] = sma_20 + (std_20 * 2)
        data['bb_middle'] = sma_20
        data['bb_lower'] = sma_20 - (std_20 * 2)
        
        # Stochastic Oscillator
        low_14 = data['low'].rolling(window=14).min()
        high_14 = data['high'].rolling(window=14).max()
        data['stoch_k'] = 100 * ((data['close'] - low_14) / (high_14 - low_14))
        data['stoch_d'] = data['stoch_k'].rolling(window=3).mean()
        
        # Williams %R
        data['williams_r'] = -100 * ((high_14 - data['close']) / (high_14 - low_14))
        
        # Volume indicators
        data['volume_ma'] = data['volume'].rolling(window=20).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Momentum
        data['momentum'] = data['close'] / data['close'].shift(10) - 1
        data['roc'] = data['close'].pct_change(10) * 100
        
        # Commodity Channel Index (CCI)
        tp = (data['high'] + data['low'] + data['close']) / 3
        sma_tp = tp.rolling(window=20).mean()
        mad_tp = tp.rolling(window=20).apply(lambda x: np.mean(np.abs(x - x.mean())))
        data['cci'] = (tp - sma_tp) / (0.015 * mad_tp)
        
        print(f"   📊 Calculados {len([col for col in data.columns if col not in ['open', 'high', 'low', 'close', 'volume']])} indicadores técnicos")
        
        return data

    def _calculate_psar(self, df: pd.DataFrame) -> pd.Series:
        """Calcula PSAR simplificado"""
        high = df['high'].values
        low = df['low'].values

        psar = np.zeros(len(df))
        psar[0] = low[0]

        acceleration = 0.02
        max_acceleration = 0.2

        trend = 1
        extreme_point = high[0]

        for i in range(1, len(df)):
            psar[i] = psar[i-1] + acceleration * (extreme_point - psar[i-1])

            if trend == 1:
                if low[i] <= psar[i]:
                    trend = -1
                    psar[i] = extreme_point
                    extreme_point = low[i]
                    acceleration = 0.02
                else:
                    if high[i] > extreme_point:
                        extreme_point = high[i]
                        acceleration = min(acceleration + 0.02, max_acceleration)
            else:
                if high[i] >= psar[i]:
                    trend = 1
                    psar[i] = extreme_point
                    extreme_point = high[i]
                    acceleration = 0.02
                else:
                    if low[i] < extreme_point:
                        extreme_point = low[i]
                        acceleration = min(acceleration + 0.02, max_acceleration)

        return pd.Series(psar, index=df.index)

    def run_strategy_comparison(self, data: pd.DataFrame, symbol: str) -> Dict:
        """
        Ejecuta todas las estrategias y compara resultados
        """
        print(f"🚀 Ejecutando comparación de estrategias para {symbol}")
        print("=" * 60)

        results = {}

        for name, strategy_info in self.strategies.items():
            print(f"📊 Ejecutando {name}...")

            try:
                strategy_class = strategy_info['class']
                config = strategy_info['config']

                # Instanciar estrategia
                if config:
                    strategy = strategy_class(config)
                else:
                    strategy = strategy_class()

                # Ejecutar backtest
                if hasattr(strategy, 'run_backtest'):
                    result = strategy.run_backtest(data, symbol)
                elif hasattr(strategy, 'run'):
                    result = strategy.run(data, symbol)
                else:
                    print(f"❌ {name}: No tiene método de backtest")
                    continue

                if 'error' not in result:
                    results[name] = result
                    print(f"✅ {name}: Retorno Total: {result.get('total_return', 0):.1f}%")
                else:
                    print(f"❌ {name}: {result['error']}")

            except Exception as e:
                print(f"❌ {name}: Error - {str(e)}")
                continue

        self.results = results
        return results

    def calculate_risk_metrics(self, trades: List[Dict]) -> Dict:
        """Calcula métricas de riesgo avanzadas"""
        if not trades:
            return {}

        pnl_series = pd.Series([t['pnl'] for t in trades])

        # Sharpe Ratio
        if len(pnl_series) > 1:
            sharpe_ratio = pnl_series.mean() / pnl_series.std() * np.sqrt(252) if pnl_series.std() > 0 else 0
        else:
            sharpe_ratio = 0

        # Sortino Ratio (solo pérdidas)
        downside_returns = pnl_series[pnl_series < 0]
        if len(downside_returns) > 0:
            sortino_ratio = pnl_series.mean() / downside_returns.std() * np.sqrt(252)
        else:
            sortino_ratio = 0

        # Calmar Ratio
        if len(pnl_series) > 2:
            cum_returns = pnl_series.cumsum()
            peak = cum_returns.expanding().max()
            drawdown = cum_returns - peak
            max_dd = abs(drawdown.min())
            calmar_ratio = pnl_series.mean() * 252 / max_dd if max_dd > 0 else 0
        else:
            calmar_ratio = 0

        # Win/Loss Ratio
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]

        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if losing_trades else 0

        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Profit Factor
        total_win = sum([t['pnl'] for t in winning_trades])
        total_loss = abs(sum([t['pnl'] for t in losing_trades]))
        profit_factor = total_win / total_loss if total_loss > 0 else 0

        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'win_loss_ratio': win_loss_ratio,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_win_amount': total_win,
            'total_loss_amount': total_loss
        }

    def generate_comparison_report(self) -> str:
        """Genera un reporte completo de comparación"""
        if not self.results:
            return "No hay resultados para comparar"

        report = []
        report.append("📊 REPORTE DE COMPARACIÓN DE ESTRATEGIAS")
        report.append("=" * 60)

        # Tabla de resumen
        report.append("\n🏆 RESUMEN GENERAL")
        report.append("-" * 60)

        summary_data = []
        for name, result in self.results.items():
            if 'error' in result:
                continue

            # Calcular métricas de riesgo
            risk_metrics = self.calculate_risk_metrics(result.get('trades', []))

            summary_data.append({
                'Estrategia': name,
                'Trades': result.get('total_trades', 0),
                'Win Rate': ".1%",
                'Total P&L': ".2f",
                'Return': ".1f",
                'Sharpe': ".2f",
                'Profit Factor': ".2f"
            })

        # Ordenar por retorno
        summary_data.sort(key=lambda x: x['Return'], reverse=True)

        # Mostrar tabla
        headers = ['Estrategia', 'Trades', 'Win Rate', 'Total P&L', 'Return', 'Sharpe', 'Profit Factor']
        report.append(" | ".join(headers))
        report.append("-" * len(" | ".join(headers)))

        for row in summary_data:
            report.append(" | ".join([str(row[h]) for h in headers]))

        # Análisis detallado
        report.append("\n\n📈 ANÁLISIS DETALLADO")
        report.append("-" * 60)

        for name, result in self.results.items():
            if 'error' in result:
                continue

            risk_metrics = self.calculate_risk_metrics(result.get('trades', []))

            report.append(f"\n🔹 {name}")
            report.append("-" * 30)
            report.append(f"   Trades Totales: {result.get('total_trades', 0)}")
            report.append(f"   Win Rate: {result.get('win_rate', 0):.1%}")
            report.append(f"   P&L Total: ${result.get('total_pnl', 0):.2f}")
            report.append(f"   Retorno Total: {result.get('total_return', 0):.1f}%")
            report.append(f"   Sharpe Ratio: {risk_metrics.get('sharpe_ratio', 0):.2f}")
            report.append(f"   Profit Factor: {risk_metrics.get('profit_factor', 0):.2f}")
            report.append(f"   Win/Loss Ratio: {risk_metrics.get('win_loss_ratio', 0):.2f}")

            if 'avg_trade_pnl' in result:
                report.append(f"   P&L Promedio por Trade: ${result.get('avg_trade_pnl', 0):.2f}")

        # Recomendaciones
        report.append("\n\n🎯 RECOMENDACIONES")
        report.append("-" * 60)

        if summary_data:
            best_strategy = summary_data[0]['Estrategia']
            best_return = summary_data[0]['Return']

            report.append(f"🥇 Mejor Estrategia: {best_strategy}")
            report.append(f"   Retorno: {best_return}%")

            # Analizar estabilidad
            returns = []
            for row in summary_data:
                return_str = str(row['Return']).replace('%', '').strip()
                try:
                    returns.append(float(return_str))
                except ValueError:
                    returns.append(0.0)  # Valor por defecto si no se puede convertir

            if returns:
                return_std = np.std(returns)
                if return_std < 5:
                    report.append("   📊 El conjunto de estrategias muestra consistencia")
                else:
                    report.append("   ⚠️ Alta variabilidad entre estrategias")
            else:
                report.append("   ⚠️ No hay datos suficientes para analizar estabilidad")

            # Recomendaciones específicas
            report.append("\n💡 RECOMENDACIONES ESPECÍFICAS:")

            for row in summary_data[:3]:  # Top 3
                strategy = row['Estrategia']
                win_rate_str = str(row['Win Rate']).replace('%', '').strip()
                profit_factor_str = str(row['Profit Factor']).replace('%', '').strip()

                try:
                    win_rate = float(win_rate_str)
                    profit_factor = float(profit_factor_str)
                except ValueError:
                    win_rate = 0.0
                    profit_factor = 0.0

                if win_rate > 60 and profit_factor > 1.5:
                    report.append(f"   ✅ {strategy}: Excelente candidato para live trading")
                elif win_rate > 50 and profit_factor > 1.2:
                    report.append(f"   🔶 {strategy}: Bueno para backtesting adicional")
                else:
                    report.append(f"   ⚠️ {strategy}: Requiere optimización adicional")

        return "\n".join(report)

    def save_comparison_report(self, filename: str = "strategy_comparison_report.txt"):
        """Guarda el reporte en un archivo"""
        report = self.generate_comparison_report()

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✅ Reporte guardado en: {filename}")

    def combine_results(self, all_results: Dict[str, Dict]) -> Dict:
        """Combina resultados de múltiples símbolos"""
        combined = {}

        for symbol, results in all_results.items():
            for strategy_name, strategy_result in results.items():
                if strategy_name not in combined:
                    combined[strategy_name] = {
                        'total_return': 0,
                        'win_rate': 0,
                        'profit_factor': 0,
                        'symbols_tested': [],
                        'results_by_symbol': {}
                    }

                if 'error' not in strategy_result:
                    combined[strategy_name]['total_return'] += strategy_result.get('total_return', 0)
                    combined[strategy_name]['win_rate'] += strategy_result.get('win_rate', 0)
                    combined[strategy_name]['profit_factor'] += strategy_result.get('profit_factor', 0)
                    combined[strategy_name]['symbols_tested'].append(symbol)
                    combined[strategy_name]['results_by_symbol'][symbol] = strategy_result

        # Calcular promedios
        num_symbols = len(all_results)
        for strategy_name in combined:
            if combined[strategy_name]['symbols_tested']:
                combined[strategy_name]['avg_return'] = combined[strategy_name]['total_return'] / num_symbols
                combined[strategy_name]['avg_win_rate'] = combined[strategy_name]['win_rate'] / num_symbols
                combined[strategy_name]['avg_profit_factor'] = combined[strategy_name]['profit_factor'] / num_symbols

        return combined

    def generate_combined_report(self, combined_results: Dict, symbols: List[str]) -> str:
        """Genera reporte combinado de múltiples símbolos"""
        report = []
        report.append("📊 REPORTE DE COMPARACIÓN DE ESTRATEGIAS")
        report.append("=" * 80)
        report.append(f"Símbolos analizados: {', '.join(symbols)}")
        report.append(f"Total de estrategias: {len(combined_results)}")
        report.append("")

        # Ordenar por retorno promedio
        sorted_strategies = sorted(
            [(name, data) for name, data in combined_results.items() if 'avg_return' in data],
            key=lambda x: x[1]['avg_return'],
            reverse=True
        )

        if sorted_strategies:
            report.append("🏆 RANKING POR RETORNO PROMEDIO")
            report.append("-" * 80)
            report.append("<15")
            report.append("-" * 80)

            for i, (strategy_name, data) in enumerate(sorted_strategies[:10], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                report.append("<15")

            report.append("")
            report.append("📈 ANÁLISIS DETALLADO")
            report.append("-" * 80)

            for strategy_name, data in sorted_strategies[:5]:
                report.append(f"\n🔍 {strategy_name}")
                report.append(f"   Retorno Promedio: {data['avg_return']:.2f}%")
                report.append(f"   Win Rate Promedio: {data['avg_win_rate']:.1f}%")
                report.append(f"   Profit Factor Promedio: {data['avg_profit_factor']:.2f}")
                report.append(f"   Símbolos probados: {len(data['symbols_tested'])}")

                # Mostrar resultados por símbolo
                for symbol, result in data['results_by_symbol'].items():
                    report.append(f"      {symbol}: {result.get('total_return', 0):.2f}% return")

        return "\n".join(report)

    def _generate_synthetic_data(self, symbol: str) -> pd.DataFrame:
        """Genera datos sintéticos como fallback"""
        print(f"📊 Generando datos sintéticos para {symbol}")
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=500, freq='1H')

        # Parámetros según el símbolo
        if 'BTC' in symbol:
            base_price = 30000
            volatility = 0.02
            volume_base = 1000000
        elif 'ETH' in symbol:
            base_price = 2000
            volatility = 0.025
            volume_base = 800000
        elif 'AAPL' in symbol:
            base_price = 150
            volatility = 0.015
            volume_base = 50000000
        elif 'TSLA' in symbol:
            base_price = 200
            volatility = 0.03
            volume_base = 30000000
        else:
            base_price = 100
            volatility = 0.02
            volume_base = 1000000

        # Generar precios
        price_changes = np.random.normal(0.0001, volatility, len(dates))
        prices = base_price * np.exp(np.cumsum(price_changes))

        # Generar OHLCV
        high_mult = 1 + np.random.uniform(0, 0.01, len(dates))
        low_mult = 1 - np.random.uniform(0, 0.01, len(dates))

        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * (1 + np.random.normal(0, 0.005, len(dates))),
            'high': prices * high_mult,
            'low': prices * low_mult,
            'close': prices,
            'volume': volume_base * (1 + np.random.uniform(0, 2, len(dates)))
        })

        df.set_index('timestamp', inplace=True)
        return self._calculate_missing_indicators(df, ['atr', 'sar', 'rsi', 'ema_10', 'ema_20', 'ema_200'])

    def _calculate_missing_indicators(self, df: pd.DataFrame, indicators: list) -> pd.DataFrame:
        """Calcula indicadores técnicos faltantes"""
        data = df.copy()
        
        for indicator in indicators:
            if indicator == 'ema_10':
                data['ema_10'] = data['close'].ewm(span=10).mean()
            elif indicator == 'ema_20':
                data['ema_20'] = data['close'].ewm(span=20).mean()
            elif indicator == 'ema_200':
                data['ema_200'] = data['close'].ewm(span=200).mean()
            elif indicator == 'atr':
                # Calcular ATR
                high = data['high']
                low = data['low']
                close = data['close']
                tr1 = high - low
                tr2 = abs(high - close.shift(1))
                tr3 = abs(low - close.shift(1))
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                data['atr'] = tr.rolling(window=14).mean()
            elif indicator == 'sar':
                data['sar'] = self._calculate_psar(data)
            elif indicator == 'rsi':
                # Calcular RSI simplificado
                delta = data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                data['rsi'] = 100 - (100 / (1 + rs))
        
        return data

def main():
    """Función principal para ejecutar comparación"""
    print("🚀 INICIANDO COMPARACIÓN DE ESTRATEGIAS")
    print("=" * 60)

    # Crear comparador
    comparator = StrategyComparator()

    # Agregar estrategias existentes
    print("📦 Cargando estrategias existentes...")

    comparator.add_strategy("UT Bot Básico", UTBotPSARStrategy)
    comparator.add_strategy("UT Bot Conservador", UTBotPSARConservativeStrategy)
    comparator.add_strategy("UT Bot Optimizado", UTBotPSAROptimizedStrategy)
    comparator.add_strategy("UT Bot Avanzado", AdvancedUTBotStrategy)
    comparator.add_strategy("Estrategia Optimizada", UTBotPSAROptimized)

    # Agregar estrategias alternativas
    print("🆕 Cargando estrategias alternativas...")

    comparator.add_strategy("ML Adaptativo", MLAdaptiveUTBotStrategy, AdaptiveStrategyConfig())
    comparator.add_strategy("Multi-Timeframe + Sentimiento", SentimentMultiTimeframeStrategy)
    comparator.add_strategy("Arbitraje Estadístico", StatisticalArbitrageStrategy, StatisticalArbitrageConfig())
    comparator.add_strategy("Momentum + Volumen", MomentumVolumeStrategy, MomentumVolumeConfig())

    # Símbolos para comparación (2 crypto + 2 acciones)
    symbols = ["BTC/USDT", "ETH/USDT", "AAPL", "TSLA"]

    all_results = {}

    for symbol in symbols:
        print(f"\n📊 Procesando {symbol}...")
        print("-" * 30)

        # Cargar datos de prueba
        data = comparator.load_real_data(symbol)
        print(f"   Datos cargados: {len(data)} filas")

        # Ejecutar comparación
        results = comparator.run_strategy_comparison(data, symbol)

        # Almacenar resultados por símbolo
        all_results[symbol] = results

    # Combinar resultados de todos los símbolos
    print("\n📋 COMBINANDO RESULTADOS...")
    combined_results = comparator.combine_results(all_results)

    # Generar y mostrar reporte
    print("\n📋 GENERANDO REPORTE FINAL...")
    report = comparator.generate_combined_report(combined_results, symbols)
    print(report)

    # Guardar reporte
    comparator.save_comparison_report()

    print("\n✅ COMPARACIÓN COMPLETADA")
    print("📄 Reporte guardado en: strategy_comparison_report.txt")

if __name__ == "__main__":
    main()
