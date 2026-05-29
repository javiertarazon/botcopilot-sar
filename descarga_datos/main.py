#!/usr/bin/env python3
"""
🤖 Bot Trader Copilot - Sistema de Backtesting Masivo
======================================================

Sistema centralizado para ejecutar backtesting de múltiples símbolos
con configuración flexible de período, temporalidad y estrategias.

Características:
- Soporte para acciones (MT5) y criptomonedas (CCXT)
- Configuración centralizada de símbolos y parámetros
- Backtesting masivo con múltiples estrategias
- Reportes detallados y comparación de resultados
"""

import asyncio
import pandas as pd
from datetime import datetime
import os
import sys
import subprocess
import time
import webbrowser
import socket
import json
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# Agregar el directorio del proyecto al path
project_root = os.path.dirname(os.path.abspath(__file__))
parent_root = os.path.dirname(project_root)  # Carpeta padre
grandparent_root = os.path.dirname(parent_root)  # Carpeta abuelo donde está dash2.py
sys.path.append(project_root)
sys.path.append(parent_root)
sys.path.append(grandparent_root)

from core.downloader import AdvancedDataDownloader
from indicators.technical_indicators import TechnicalIndicators
from utils.normalization import DataNormalizer
from utils.storage import DataStorage, save_to_csv
from config.config_loader import load_config_from_yaml, get_active_exchanges, get_enabled_strategies
from utils.logger import setup_logging, get_logger
from strategies.ut_bot_psar import UTBotPSARStrategy
from strategies.optimized_utbot_strategy import OptimizedUTBotStrategy
from backtesting.backtester import AdvancedBacktester
from execution.paper_trader import run_paper_trading_for_symbol
from execution.live_trader import run_live_trading, LiveTradingConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot Trader Copilot")
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper", "live", "optimize"],
        default="backtest",
        help="Modo de ejecución (default: backtest)",
    )
    parser.add_argument("--symbols", nargs="*", help="Override de símbolos (ej: BTC/USDT ETH/USDT)")
    parser.add_argument("--symbol", help="Símbolo único (útil para live)")
    parser.add_argument("--timeframe", help="Override timeframe (ej: 1h, 15m)")
    parser.add_argument("--start-date", help="Override start_date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Override end_date (YYYY-MM-DD)")
    parser.add_argument("--exchange", help="Override active_exchange (ej: okx, bybit, binance)")
    parser.add_argument("--paper-allow-short", action="store_true", help="Permite short en paper trading")
    parser.add_argument("--live-poll-seconds", type=int, default=30, help="Polling en live (segundos)")
    parser.add_argument("--strategy", choices=["basica", "conservadora", "optimizada"], help="Estrategia para optimize/live")
    parser.add_argument("--opt-iters", type=int, default=200, help="Iteraciones de optimización (random search)")
    parser.add_argument("--opt-seed", type=int, default=42, help="Seed para optimización")
    parser.add_argument("--opt-data-url", help="URL CSV OHLCV (default: SOLUSDT_1h dataset)")
    parser.add_argument("--opt-top", type=int, default=10, help="Top N resultados a mostrar/guardar")
    return parser.parse_args(argv)

def check_python_processes(logger=None):
    """
    Verifica si hay procesos Python ejecutándose que puedan interferir.
    """
    try:
        import subprocess
        # Obtener todos los procesos Python con información detallada
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/V'],
                              capture_output=True, text=True)

        python_processes = []
        lines = result.stdout.split('\n')

        for line in lines[3:]:  # Saltar encabezados
            if line.strip() and 'python.exe' in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = parts[1]
                        # Solo agregar PIDs válidos
                        if pid.isdigit():
                            python_processes.append(pid)
                    except (ValueError, IndexError):
                        continue

        # También verificar procesos que podrían estar usando el puerto 8501
        try:
            netstat_result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            for line in netstat_result.stdout.split('\n'):
                if ':8501' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit() and pid not in python_processes:
                            python_processes.append(pid)
                            if logger:
                                logger.info(f"🔍 Proceso usando puerto 8501 encontrado: PID {pid}")
        except Exception as e:
            if logger:
                logger.warning(f"No se pudo verificar procesos en puerto 8501: {e}")

        if python_processes:
            if logger:
                logger.info(f"🔍 Encontrados {len(python_processes)} procesos Python: {', '.join(python_processes)}")
            return python_processes
        else:
            if logger:
                logger.info("✅ No hay procesos Python conflictivos")
            return []

    except Exception as e:
        if logger:
            logger.warning(f"No se pudo verificar procesos Python: {e}")
        return []

def check_streamlit_processes(logger=None):
    """
    Verifica específicamente procesos de Streamlit que puedan estar ejecutándose.
    """
    try:
        import subprocess
        # Buscar procesos que contengan "streamlit" en el comando
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/V'],
                              capture_output=True, text=True)

        streamlit_processes = []
        lines = result.stdout.split('\n')

        for line in lines:
            if 'streamlit' in line.lower():
                # Extraer PID de la línea
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = parts[1]
                        streamlit_processes.append(pid)
                    except (ValueError, IndexError):
                        continue

        if streamlit_processes:
            if logger:
                logger.info(f"🔍 Encontrados {len(streamlit_processes)} procesos Streamlit: {', '.join(streamlit_processes)}")
            return streamlit_processes
        else:
            if logger:
                logger.info("✅ No hay procesos Streamlit ejecutándose")
            return []

    except Exception as e:
        if logger:
            logger.warning(f"No se pudo verificar procesos Streamlit: {e}")
        return []

def check_port_availability(port=8501, logger=None):
    """
    Verifica si el puerto especificado está disponible.
    """
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # Timeout de 5 segundos

        result = sock.connect_ex(('localhost', port))
        sock.close()

        if result == 0:
            if logger:
                logger.warning(f"⚠️ Puerto {port} está ocupado")
            return False
        else:
            if logger:
                logger.info(f"✅ Puerto {port} está disponible")
            return True

    except socket.timeout:
        if logger:
            logger.warning(f"Timeout verificando puerto {port}")
        return False
    except Exception as e:
        if logger:
            logger.warning(f"No se pudo verificar puerto {port}: {e}")
        return True  # Asumir disponible si no se puede verificar

def kill_conflicting_processes(processes, logger=None):
    """
    Mata procesos conflictivos de Python.
    """
    try:
        import subprocess
        killed_count = 0
        failed_count = 0

        for pid in processes:
            try:
                # Usar taskkill con más opciones para asegurar terminación
                result = subprocess.run(['taskkill', '/PID', str(pid), '/F', '/T'],
                                      capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    killed_count += 1
                    if logger:
                        logger.info(f"🛑 Proceso Python {pid} terminado exitosamente")
                else:
                    failed_count += 1
                    if logger:
                        logger.warning(f"No se pudo terminar proceso {pid}: {result.stderr}")

            except subprocess.TimeoutExpired:
                failed_count += 1
                if logger:
                    logger.warning(f"Timeout terminando proceso {pid}")
            except Exception as e:
                failed_count += 1
                if logger:
                    logger.warning(f"Error terminando proceso {pid}: {e}")

        if logger:
            if killed_count > 0:
                logger.info(f"✅ Terminados {killed_count} procesos conflictivos exitosamente")
            if failed_count > 0:
                logger.warning(f"⚠️ No se pudieron terminar {failed_count} procesos")

        return killed_count

    except Exception as e:
        if logger:
            logger.error(f"Error general terminando procesos: {e}")
        return 0

def force_cleanup_port_8501(logger=None):
    """
    Fuerza la liberación del puerto 8501 usando comandos del sistema operativo.
    """
    try:
        import subprocess

        success = False

        # Método 1: Usar netstat y taskkill para encontrar y matar procesos usando el puerto
        try:
            logger.info("🔧 Método 1: Liberando puerto usando netstat + taskkill...")

            # Encontrar procesos usando el puerto 8501
            netstat_result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=10)

            pids_to_kill = []
            for line in netstat_result.stdout.split('\n'):
                if ':8501' in line and ('LISTENING' in line or 'ESTABLISHED' in line):
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit() and pid not in pids_to_kill:
                            pids_to_kill.append(pid)

            # Matar los procesos encontrados
            for pid in pids_to_kill:
                try:
                    result = subprocess.run(['taskkill', '/PID', pid, '/F', '/T'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        if logger:
                            logger.info(f"🛑 Proceso {pid} (usando puerto 8501) terminado")
                        success = True
                    else:
                        if logger:
                            logger.warning(f"No se pudo terminar proceso {pid}: {result.stderr}")
                except Exception as e:
                    if logger:
                        logger.warning(f"Error terminando proceso {pid}: {e}")

        except Exception as e:
            if logger:
                logger.warning(f"Error en método 1: {e}")

        # Método 2: Matar todos los procesos de Python (más agresivo)
        try:
            if not success:
                logger.info("🔧 Método 2: Terminando todos los procesos Python...")

                result = subprocess.run(['taskkill', '/IM', 'python.exe', '/F'],
                                      capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    if logger:
                        logger.info("🛑 Todos los procesos Python terminados")
                    success = True
                    time.sleep(3)  # Esperar a que se liberen los recursos
                else:
                    if logger:
                        logger.warning(f"No se pudieron terminar procesos Python: {result.stderr}")

        except Exception as e:
            if logger:
                logger.warning(f"Error en método 2: {e}")

        # Método 3: Usar comandos de red para forzar liberación
        try:
            if not success:
                logger.info("🔧 Método 3: Usando comandos de red para liberar puerto...")

                # En Windows, intentar resetear el puerto
                result = subprocess.run(['netsh', 'interface', 'ipv4', 'reset'],
                                      capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    if logger:
                        logger.info("🔄 Interfaces de red reseteadas")
                    success = True
                    time.sleep(2)
                else:
                    if logger:
                        logger.warning(f"No se pudieron resetear interfaces: {result.stderr}")

        except Exception as e:
            if logger:
                logger.warning(f"Error en método 3: {e}")

        # Verificación final
        time.sleep(2)
        final_check = check_port_availability(8501, logger)

        if final_check:
            if logger:
                logger.info("✅ Puerto 8501 liberado exitosamente")
            return True
        else:
            if logger:
                logger.warning("⚠️ Puerto 8501 aún ocupado después de limpieza")
            return False

    except Exception as e:
        if logger:
            logger.error(f"❌ Error en limpieza forzada del puerto: {e}")
        return False

def verify_dashboard_running(logger=None):
    """
    Verifica que el dashboard esté realmente ejecutándose y respondiendo.
    """
    try:
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if requests:
                    # Usar requests si está disponible
                    response = requests.get("http://localhost:8501", timeout=5)
                    if response.status_code == 200:
                        if logger:
                            logger.info("✅ Dashboard respondiendo correctamente")
                        return True
                else:
                    # Usar socket como alternativa
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex(('localhost', 8501))
                    sock.close()
                    if result == 0:
                        if logger:
                            logger.info("✅ Dashboard respondiendo correctamente (verificación socket)")
                        return True

            except Exception as e:
                if logger:
                    logger.debug(f"Intento {attempt + 1} falló: {e}")
                pass

            if logger:
                logger.info(f"⏳ Esperando respuesta del dashboard (intento {attempt + 1}/{max_attempts})...")
            time.sleep(2)

        if logger:
            logger.warning("⚠️ Dashboard no responde después de múltiples intentos")
        return False

    except Exception as e:
        if logger:
            logger.warning(f"Error verificando dashboard: {e}")
        return False

def launch_dashboard():
    """
    Lanza el dashboard profesional con limpieza automática agresiva de puertos.
    """
    try:
        logger = get_logger(__name__)
        logger.info("🚀 Iniciando verificación previa al lanzamiento del dashboard...")

        # PASO 1: Limpieza agresiva del puerto 8501
        logger.info("🧹 Realizando limpieza agresiva del puerto 8501...")
        success = force_cleanup_port_8501(logger)
        if not success:
            logger.warning("⚠️ No se pudo liberar completamente el puerto, intentando continuar...")

        # PASO 2: Verificar procesos Python existentes
        logger.info("🔍 Verificando procesos Python existentes...")
        python_processes = check_python_processes(logger)

        # PASO 3: Verificar procesos Streamlit específicamente
        logger.info("🔍 Verificando procesos Streamlit existentes...")
        streamlit_processes = check_streamlit_processes(logger)

        # PASO 4: Combinar listas de procesos a terminar
        all_processes = list(set(python_processes + streamlit_processes))

        # PASO 5: Verificar disponibilidad del puerto con múltiples intentos
        logger.info("🔍 Verificando disponibilidad del puerto 8501...")
        port_available = False
        max_attempts = 3

        for attempt in range(max_attempts):
            port_available = check_port_availability(8501, logger)

            if port_available:
                logger.info("✅ Puerto 8501 disponible")
                break
            else:
                logger.warning(f"⚠️ Puerto ocupado (intento {attempt + 1}/{max_attempts})")

                if all_processes:
                    logger.info("🛑 Intentando terminar procesos conflictivos...")
                    killed_count = kill_conflicting_processes(all_processes, logger)

                    if killed_count > 0:
                        logger.info(f"⏳ Esperando {10 + attempt * 5} segundos para que los procesos terminen...")
                        time.sleep(10 + attempt * 5)  # Esperar más tiempo en cada intento
                    else:
                        logger.warning("❌ No se pudieron terminar procesos, intentando forzar liberación del puerto...")
                        force_cleanup_port_8501(logger)
                        time.sleep(5)
                else:
                    logger.info("🛑 No hay procesos identificados, intentando forzar liberación del puerto...")
                    force_cleanup_port_8501(logger)
                    time.sleep(5)

        if not port_available:
            logger.error("❌ No se pudo liberar el puerto 8501 después de múltiples intentos")
            logger.info("💡 Sugerencias:")
            logger.info("   1. Cierra manualmente otros procesos de Streamlit/Python")
            logger.info("   2. Reinicia tu computadora si es necesario")
            logger.info("   3. Verifica que no haya otras aplicaciones usando el puerto 8501")
            return False

        # PASO 6: Verificar que el dashboard existe
        dashboard_path = os.path.join(grandparent_root, "dash2.py")
        if not os.path.exists(dashboard_path):
            logger.error(f"❌ Dashboard no encontrado en: {dashboard_path}")
            return False

        logger.info("📊 Lanzando Dashboard Profesional...")

        # PASO 7: Ejecutar Streamlit con mejor manejo de errores
        try:
            import subprocess

            # Comando para ejecutar streamlit con opciones adicionales
            cmd = [
                sys.executable, "-m", "streamlit", "run", "dash2.py",
                "--server.port", "8501",
                "--server.headless", "true",
                "--server.address", "0.0.0.0",
                "--server.enableCORS", "false",
                "--server.enableXsrfProtection", "false"
            ]

            logger.info("📊 Ejecutando Streamlit directamente...")
            logger.info(f"📂 Directorio de trabajo: {grandparent_root}")
            logger.info(f"📄 Archivo dashboard: dash2.py")

            # Ejecutar streamlit en background con mejor configuración
            process = subprocess.Popen(
                cmd,
                cwd=grandparent_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Esperar más tiempo para que se inicie completamente
            logger.info("⏳ Esperando que Streamlit se inicie completamente...")
            time.sleep(8)

            # Verificar si está ejecutándose
            if process.poll() is None:
                logger.info("✅ Dashboard iniciado correctamente")
                logger.info("📊 Dashboard disponible en: http://localhost:8501")

                # Verificar que realmente esté respondiendo
                if verify_dashboard_running(logger):
                    # Abrir navegador
                    try:
                        import webbrowser
                        webbrowser.open("http://localhost:8501")
                        logger.info("🌐 Navegador abierto automáticamente")
                    except Exception as e:
                        logger.warning(f"No se pudo abrir navegador: {e}")

                    return True
                else:
                    logger.error("❌ Dashboard no responde correctamente")
                    process.terminate()
                    return False
            else:
                # Si falló, obtener el error
                stdout, stderr = process.communicate()
                logger.error("❌ Error iniciando dashboard:")
                if stderr:
                    logger.error(f"STDERR: {stderr}")
                if stdout:
                    logger.info(f"STDOUT: {stdout}")
                return False

        except Exception as e:
            logger.error(f"❌ Error lanzando dashboard: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Error general en launch_dashboard: {e}")
        return False

def validate_data(df: pd.DataFrame, logger=None) -> bool:
    """
    Valida la integridad de los datos antes del backtesting.
    """
    if logger is None:
        logger = get_logger(__name__)

    if df.empty:
        logger.error("El DataFrame está vacío")
        return False

    required_columns = ['open', 'high', 'low', 'close', 'volume']
    technical_columns = ['sar', 'atr', 'adx']
    all_required = required_columns + technical_columns

    missing_columns = [col for col in all_required if col not in df.columns]
    if missing_columns:
        logger.error(f"Faltan columnas requeridas: {missing_columns}")
        return False

    # Verificar valores nulos
    null_check = df[required_columns].isnull().any()
    if null_check.any():
        null_cols = null_check[null_check].index.tolist()
        logger.error(f"Hay valores nulos en las columnas OHLCV: {null_cols}")
        return False

    logger.info("Validación de datos completada exitosamente")
    return True

async def download_symbol_data(symbol: str, config,
                             downloader, mt5_downloader, logger):
    """
    Descarga datos para un símbolo específico usando la fuente apropiada.
    """
    timeframe = config.backtesting.timeframe
    start_date = config.backtesting.start_date
    end_date = config.backtesting.end_date

    try:
        if symbol.endswith('.US'):
            # Acción - usar MT5 si está disponible
            if mt5_downloader is not None:
                logger.info(f"[INFO] Descargando {symbol} desde MT5...")

                # Convertir fechas
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')

                ohlcv_data = await mt5_downloader.download_data(
                    symbol.replace('.US', ''), timeframe, start_dt, end_dt
                )

                if ohlcv_data is not None and not ohlcv_data.empty:
                    logger.info(f"[SUCCESS] Datos descargados desde MT5: {len(ohlcv_data)} velas")
                    return ohlcv_data
                else:
                    logger.warning(f"[WARNING] No se pudieron descargar datos de MT5 para {symbol}")

        else:
            # Criptomoneda - usar CCXT
            logger.info(f"[INFO] Descargando {symbol} desde CCXT...")

            ohlcv_data, stats = await downloader.async_download_ohlcv(
                symbol, config.active_exchange, timeframe=timeframe, limit=1000
            )

            if ohlcv_data is not None and not ohlcv_data.empty:
                logger.info(f"[SUCCESS] Datos descargados desde CCXT: {len(ohlcv_data)} velas")
                return ohlcv_data
            else:
                logger.warning(f"[WARNING] No se pudieron descargar datos de CCXT para {symbol}")

    except Exception as e:
        logger.error(f"[ERROR] Error descargando {symbol}: {e}")

    return None

async def process_symbol_backtest(data: pd.DataFrame, symbol: str, config, logger) -> dict:
    """
    Procesa el backtesting completo para un símbolo con datos ya descargados.
    """
    try:
        if data is None or data.empty:
            logger.error(f"No hay datos disponibles para {symbol}")
            return {}

        # Los datos ya incluyen indicadores calculados y normalizados
        data_with_indicators = data

        # 1. Validar datos
        if not validate_data(data_with_indicators, logger):
            logger.error(f"Datos inválidos para {symbol}")
            return {}

        # 2. Ejecutar backtesting
        logger.info(f"[INFO] Ejecutando backtesting para {symbol}...")
        results = await run_backtest(data_with_indicators, symbol, config)

        if results:
            logger.info(f"[SUCCESS] Backtesting completado exitosamente para {symbol}")
            
            # Guardar resultados para el dashboard
            print(f"[DEBUG] Llamando a save_backtest_results para {symbol}")
            await save_backtest_results(results, symbol, config, logger)
            
            return results
        else:
            logger.warning(f"[WARNING] Backtesting sin resultados para {symbol}")
            return {}

    except Exception as e:
        logger.error(f"[ERROR] Error procesando {symbol}: {e}")
        return {}

async def run_backtest(data: pd.DataFrame, symbol: str, config) -> dict:
    """
    Ejecuta el backtesting con la estrategia unificada usando diferentes estilos.
    """
    logger = get_logger(__name__)

    # Importar estrategias individuales
    from strategies.ut_bot_psar import UTBotPSARStrategy
    from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy
    from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy

    # Configuraciones de estrategia basadas en la configuración
    strategies = {}

    enabled_strategies = get_enabled_strategies(config)
    logger.info(f"[DEBUG] Estrategias habilitadas: {enabled_strategies}")
    logger.info(f"[DEBUG] Número de estrategias habilitadas: {len(enabled_strategies)}")

    # Crear estrategias individuales
    if "Estrategia_Basica" in enabled_strategies:
        strategies["Estrategia_Basica"] = UTBotPSARStrategy()

    if "Estrategia_Conservadora" in enabled_strategies:
        strategies["Estrategia_Conservadora"] = UTBotPSARConservativeStrategy()

    if "Estrategia_Optimizada" in enabled_strategies:
        strategies["Estrategia_Optimizada"] = UTBotPSAROptimizedStrategy()

    logger.info(f"[DEBUG] Estrategias configuradas: {list(strategies.keys())}")
    logger.info(f"[DEBUG] Número de estrategias configuradas: {len(strategies)}")

    results = {}

    for strategy_name, strategy in strategies.items():
        logger.info(f"[INFO] Probando estrategia: {strategy_name}")

        backtester = AdvancedBacktester(
            initial_capital=config.backtesting.initial_capital,
            commission=config.backtesting.commission
        )

        strategy_results = backtester.run(strategy, data, symbol)
        results[strategy_name] = strategy_results

        # Log básico de resultados
        pnl = strategy_results.get('total_pnl', 0)
        win_rate = strategy_results.get('win_rate', 0) * 100
        logger.info(f"[SUCCESS] Backtesting completado para {symbol}: {len(strategy_results.get('trades', []))} trades, P&L: ${pnl:.2f}, Win Rate: {win_rate:.1f}%")

    return results

def generate_backtest_report(results: dict, config, logger):
    """
    Genera un reporte final del backtesting masivo.
    """
    logger.info(f"\n{'='*80}")
    logger.info("[INFO] REPORTE FINAL DE BACKTESTING MASIVO")
    logger.info(f"{'='*80}")

    if not results:
        logger.warning("No hay resultados para mostrar")
        return

    # Análisis por símbolo
    logger.info(f"\n[INFO] RESULTADOS POR SIMBOLO:")
    logger.info("-" * 80)
    logger.info(f"{'Símbolo':15s} | {'Mejor Estrategia':20s} | {'P&L':10s} | {'Win Rate':8s} | {'Max DD':8s}")
    logger.info("-" * 80)

    symbol_summary = []
    for symbol, strategies in results.items():
        best_strategy = max(strategies.items(), key=lambda x: x[1].get('total_pnl', -10000))
        strategy_name, result = best_strategy

        pnl = result.get('total_pnl', 0)
        win_rate = result.get('win_rate', 0) * 100
        max_dd = result.get('max_drawdown', 0) * 100

        symbol_summary.append({
            'symbol': symbol,
            'strategy': strategy_name,
            'pnl': pnl,
            'win_rate': win_rate,
            'max_dd': max_dd
        })

        logger.info(f"{symbol:15s} | {strategy_name:20s} | ${pnl:10.2f} | {win_rate:6.1f}% | {max_dd:6.1f}%")

    # Ranking final
    logger.info(f"\n[INFO] RANKING FINAL (ordenado por P&L):")
    logger.info("-" * 80)
    logger.info(f"{'Posición':8s} | {'Símbolo':10s} | {'Estrategia':20s} | {'P&L':10s} | {'Win Rate':8s}")
    logger.info("-" * 80)

    sorted_symbols = sorted(symbol_summary, key=lambda x: x['pnl'], reverse=True)

    for i, item in enumerate(sorted_symbols, 1):
        medal = "[1st]" if i == 1 else "[2nd]" if i == 2 else "[3rd]" if i == 3 else f"{i:2d}"
        logger.info(f"{medal} | {item['symbol']:10s} | {item['strategy']:20s} | ${item['pnl']:10.2f} | {item['win_rate']:6.1f}%")

    # Estadísticas generales
    total_pnl = sum(item['pnl'] for item in symbol_summary)
    avg_win_rate = sum(item['win_rate'] for item in symbol_summary) / len(symbol_summary)
    profitable_symbols = sum(1 for item in symbol_summary if item['pnl'] > 0)

    logger.info(f"\n[INFO] ESTADISTICAS GENERALES:")
    logger.info(f"   • Símbolos procesados: {len(symbol_summary)}")
    logger.info(f"   • Símbolos rentables: {profitable_symbols}")
    logger.info(f"   • P&L Total: ${total_pnl:.2f}")
    logger.info(f"   • Win Rate Promedio: {avg_win_rate:.1f}%")
    logger.info(f"   • Temporalidad: {config.backtesting.timeframe}")
    logger.info(f"   • Periodo: {config.backtesting.start_date} a {config.backtesting.end_date}")

    # === SISTEMA DE COMPENSACIÓN DESACTIVADO ===
    logger.info(f"\n[INFO] SISTEMA DE COMPENSACIÓN: DESACTIVADO")
    logger.info(f"   • No se aplican compensaciones a los resultados")
    logger.info(f"   • Se muestran resultados puros de las estrategias")

    logger.info(f"\n{'='*80}")

async def main():
    """
    Función principal del sistema de backtesting masivo.
    """
    args = parse_args()
    # Cargar configuración centralizada
    config = load_config_from_yaml()

    # Overrides por CLI (para paper/live también)
    if args.timeframe:
        config.backtesting.timeframe = args.timeframe
    if args.start_date:
        config.backtesting.start_date = args.start_date
    if args.end_date:
        config.backtesting.end_date = args.end_date
    if args.symbols:
        config.backtesting.symbols = args.symbols
    if args.symbol:
        config.backtesting.symbols = [args.symbol]
    if args.exchange:
        config.active_exchange = args.exchange
        # Asegurar que el exchange seleccionado esté habilitado para esta ejecución
        if args.exchange in config.exchanges:
            for name, ex_cfg in config.exchanges.items():
                ex_cfg.enabled = (name == args.exchange)

    # Configurar logging
    setup_logging(config.system.log_level, config.system.log_file)
    logger = get_logger(__name__)

    logger.info(f"[INFO] Iniciando Bot Trader Copilot (mode={args.mode})")
    logger.info("=" * 60)

    # Mostrar configuración actual
    active_symbols = config.backtesting.symbols
    logger.info(f"[INFO] Simbolos a procesar: {len(active_symbols)}")
    logger.info(f"[INFO] Temporalidad: {config.backtesting.timeframe}")
    logger.info(f"[INFO] Periodo: {config.backtesting.start_date} a {config.backtesting.end_date}")
    logger.info(f"[INFO] Capital inicial: ${config.backtesting.initial_capital}")
    enabled_strategies = get_enabled_strategies(config)
    logger.info(f"[INFO] Estrategias activas: {len(enabled_strategies)}")
    logger.info("=" * 60)

    # Live: no requiere precarga masiva (usa polling), pero sí exchange activo
    if args.mode == "live":
        if not active_symbols:
            raise RuntimeError("Live requiere al menos un símbolo (usa --symbol o backtesting.symbols)")

        enabled_strategies = get_enabled_strategies(config)
        if not enabled_strategies:
            raise RuntimeError("No hay estrategias habilitadas en config.backtesting.strategies")

        # Elegir la primera estrategia habilitada (evita ambigüedad en live)
        strategy_name = enabled_strategies[0]
        if strategy_name == "Estrategia_Basica":
            strategy = UTBotPSARStrategy()
        elif strategy_name == "Estrategia_Conservadora":
            from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy

            strategy = UTBotPSARConservativeStrategy()
        else:
            from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy

            strategy = UTBotPSAROptimizedStrategy()

        await run_live_trading(
            strategy=strategy,
            config=config,
            logger=logger,
            live=LiveTradingConfig(
                symbol=active_symbols[0],
                timeframe=config.backtesting.timeframe,
                poll_seconds=int(args.live_poll_seconds),
                allow_short=False,
            ),
        )
        return

    # Inicializar componentes (backtest/paper)
    downloader = AdvancedDataDownloader(config)

    # Verificar MT5
    mt5_available = False
    if config.mt5.enabled:
        logger.info("[INFO] MT5 habilitado - disponible para acciones")
        mt5_available = True
    else:
        logger.info("[INFO] MT5 deshabilitado - solo criptomonedas")

    storage = DataStorage(f"{config.storage.path}/data.db")
    backtest_results = {}

    try:
        # Inicializar downloader avanzado
        success = await downloader.initialize()
        if not success:
            logger.error("No se pudo inicializar el downloader")
            return

        # Descargar datos de todos los símbolos en paralelo
        logger.info("🚀 Iniciando descarga masiva de datos...")
        symbol_data = await downloader.download_multiple_symbols(
            active_symbols,
            timeframe=config.backtesting.timeframe,
            start_date=config.backtesting.start_date,
            end_date=config.backtesting.end_date
        )

        if not symbol_data:
            logger.error("No se pudieron descargar datos de ningún símbolo")
            return

        # Procesar y guardar datos
        logger.info("💾 Procesando y guardando datos...")
        processed_symbol_data = await downloader.process_and_save_data(
            symbol_data,
            config.backtesting.timeframe,
            save_csv=True
        )

        if args.mode == "paper":
            enabled_strategies = get_enabled_strategies(config)
            if not enabled_strategies:
                raise RuntimeError("No hay estrategias habilitadas en config.backtesting.strategies")

            for symbol, df in processed_symbol_data.items():
                logger.info(f"\n{'='*60}")
                logger.info(f"Procesando paper trading: {symbol}")
                logger.info(f"{'='*60}")

                strategies = {}
                if "Estrategia_Basica" in enabled_strategies:
                    strategies["Estrategia_Basica"] = UTBotPSARStrategy()
                if "Estrategia_Conservadora" in enabled_strategies:
                    from strategies.ut_bot_psar_conservative import UTBotPSARConservativeStrategy

                    strategies["Estrategia_Conservadora"] = UTBotPSARConservativeStrategy()
                if "Estrategia_Optimizada" in enabled_strategies:
                    from strategies.ut_bot_psar_optimized import UTBotPSAROptimizedStrategy

                    strategies["Estrategia_Optimizada"] = UTBotPSAROptimizedStrategy()

                paper_results = {}
                for strategy_name, strategy in strategies.items():
                    paper_results[strategy_name] = run_paper_trading_for_symbol(
                        symbol=symbol,
                        strategy=strategy,
                        data=df,
                        config=config,
                        logger=logger,
                        allow_short=bool(args.paper_allow_short),
                    )

                await save_backtest_results(paper_results, symbol, config, logger)

            logger.info("[PAPER] Finalizado")
            return

        # === BACKTEST (comportamiento existente) ===
        backtest_results = {}
        for i, (symbol, df) in enumerate(processed_symbol_data.items(), 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Procesando backtesting {i}/{len(processed_symbol_data)}: {symbol}")
            logger.info(f"{'='*60}")

            result = await process_symbol_backtest(df, symbol, config, logger)
            if result:
                backtest_results[symbol] = result
                print(f"[DEBUG] Resultado guardado para {symbol}: {len(result)} estrategias")
            else:
                print(f"[DEBUG] No hay resultado para {symbol}")

        print(f"[DEBUG] Backtest completado. Total símbolos procesados: {len(backtest_results)}")
        generate_backtest_report(backtest_results, config, logger)

        if backtest_results:
            await save_global_summary(backtest_results, config, logger)

        if hasattr(config.system, 'auto_launch_dashboard') and config.system.auto_launch_dashboard:
            logger.info("📊 Iniciando lanzamiento automático del dashboard...")
            dashboard_launched = launch_dashboard()
            if dashboard_launched:
                logger.info("✅ Dashboard profesional iniciado exitosamente")
                logger.info("🌐 Accede a: http://localhost:8501")
            else:
                logger.warning("⚠️ No se pudo iniciar el dashboard automáticamente")
        else:
            logger.info("📊 Dashboard automático deshabilitado")
            logger.info("💡 Para ver los resultados, ejecuta: python -m streamlit run dash2.py")

    finally:
        # Cerrar conexiones
        await downloader.shutdown()

def calculate_symbol_compensation_metrics(results: dict, compensation_config: dict = None) -> dict:
    """
    Calcula métricas de compensación realistas basadas en configuración.

    Args:
        results: Resultados del backtesting por estrategia
        compensation_config: Configuración de compensación (opcional)
    """
    if compensation_config is None:
        compensation_config = {
            'enabled': True,
            'success_rate': 0.65,  # 65% de éxito en compensaciones
            'recovery_factor': 0.75,  # 75% de recuperación de pérdida
            'max_compensation_size': 0.5,  # Máximo 50% del tamaño original
            'min_trade_size': 10,  # Mínimo tamaño de trade para compensar
            'max_daily_compensations': 3,  # Máximo compensaciones por día
            'cooldown_period': 2  # Días de enfriamiento entre compensaciones
        }

    if not compensation_config.get('enabled', True):
        return {
            'compensated_trades': 0,
            'total_compensation_pnl': 0.0,
            'compensation_success_rate': 0.0,
            'adjusted_total_pnl': 0.0
        }

    print(f"[DEBUG] Función calculate_symbol_compensation_metrics llamada con configuración realista")
    logger = get_logger(__name__)
    logger.info(f"[DEBUG] Calculando métricas de compensación realistas")

    # Obtener la mejor estrategia para calcular métricas
    best_strategy = max(results.items(), key=lambda x: x[1].get('total_pnl', -10000))
    strategy_name, result = best_strategy
    print(f"[DEBUG] Mejor estrategia: {strategy_name}")

    # Obtener trades de la mejor estrategia
    trades = result.get('trades', [])
    print(f"[DEBUG] Número total de trades: {len(trades)}")

    if not trades:
        return {
            'compensated_trades': 0,
            'total_compensation_pnl': 0.0,
            'compensation_success_rate': 0.0,
            'adjusted_total_pnl': result.get('total_pnl', 0)
        }

    # Filtrar trades perdedores elegibles para compensación
    losing_trades = []
    for trade in trades:
        pnl = trade.get('pnl', 0)
        if pnl < 0:  # Trade perdedor
            # Verificar tamaño mínimo
            trade_size = abs(pnl)
            if trade_size >= compensation_config['min_trade_size']:
                losing_trades.append(trade)

    print(f"[DEBUG] Trades perdedores elegibles: {len(losing_trades)}")

    if not losing_trades:
        return {
            'compensated_trades': 0,
            'total_compensation_pnl': 0.0,
            'compensation_success_rate': 0.0,
            'adjusted_total_pnl': result.get('total_pnl', 0)
        }

    # Simular compensaciones realistas
    total_compensation_pnl = 0.0
    successful_compensations = 0
    compensation_attempts = 0

    # Procesar trades por fecha para respetar límites diarios
    trades_by_date = {}
    for trade in losing_trades:
        date = trade.get('entry_date', trade.get('date', 'unknown'))
        if date not in trades_by_date:
            trades_by_date[date] = []
        trades_by_date[date].append(trade)

    # Procesar día por día
    for date, day_trades in trades_by_date.items():
        daily_compensations = 0

        for trade in day_trades:
            if daily_compensations >= compensation_config['max_daily_compensations']:
                break  # Límite diario alcanzado

            compensation_attempts += 1

            # Calcular tamaño de compensación (limitado)
            original_loss = abs(trade.get('pnl', 0))
            max_compensation = original_loss * compensation_config['max_compensation_size']
            compensation_size = min(max_compensation, original_loss * 0.3)  # Máximo 30% del original

            # Simular resultado de compensación con probabilidad realista
            import random
            random.seed(hash(f"{date}_{compensation_attempts}"))  # Seed consistente
            compensation_success = random.random() < compensation_config['success_rate']

            if compensation_success:
                # Compensación exitosa - recupera parte de la pérdida
                recovery_amount = compensation_size * compensation_config['recovery_factor']
                compensation_pnl = recovery_amount
                successful_compensations += 1
                daily_compensations += 1
            else:
                # Compensación fallida - genera pérdida adicional pequeña
                compensation_pnl = -compensation_size * 0.2  # Solo 20% de pérdida adicional

            total_compensation_pnl += compensation_pnl

    # Calcular métricas finales
    total_losing_trades = len(losing_trades)
    compensation_success_rate = (successful_compensations / compensation_attempts) * 100 if compensation_attempts > 0 else 0
    original_pnl = result.get('total_pnl', 0)
    adjusted_total_pnl = original_pnl + total_compensation_pnl

    metrics = {
        'compensated_trades': successful_compensations,
        'total_compensation_pnl': total_compensation_pnl,
        'compensation_success_rate': compensation_success_rate,
        'adjusted_total_pnl': adjusted_total_pnl,
        'total_losing_trades': total_losing_trades,
        'compensation_attempts': compensation_attempts,
        'compensation_config': compensation_config
    }

    print(f"[DEBUG] Métricas calculadas: {metrics}")
    logger.info(f"[DEBUG] Compensación completada: {successful_compensations}/{compensation_attempts} exitosas ({compensation_success_rate:.1f}%)")

    return metrics

async def save_backtest_results(results: dict, symbol: str, config, logger):
    print(f"[DEBUG] save_backtest_results llamada para {symbol} con {len(results)} estrategias")
    try:
        # Crear directorio para resultados si no existe
        results_dir = Path("data/dashboard_results")
        results_dir.mkdir(parents=True, exist_ok=True)

        # Archivo para este símbolo
        results_file = results_dir / f"{symbol.replace('/', '_').replace('.', '_')}_results.json"

        # Preparar datos para guardar
        dashboard_data = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'strategies': {},
            'summary': {
                'total_strategies': len(results),
                'best_strategy': None,
                'best_pnl': float('-inf'),
                'total_trades': 0,
                'avg_win_rate': 0.0,
                'total_compensated_trades': 0,
                'total_compensation_pnl': 0.0,
                'avg_compensation_rate': 0.0
            }
        }

        win_rates = []
        compensation_rates = []

        # === SISTEMA DE COMPENSACIÓN COMPLETAMENTE DESACTIVADO ===
        logger.info(f"[INFO] Sistema de compensación completamente deshabilitado para {symbol}")

        for strategy_name, strategy_result in results.items():
            # Convertir datos no serializables
            clean_result = {}
            for key, value in strategy_result.items():
                if isinstance(value, pd.Series):
                    clean_result[key] = value.tolist()
                elif isinstance(value, pd.DataFrame):
                    clean_result[key] = value.to_dict('records')
                elif isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                    clean_result[key] = value
                else:
                    clean_result[key] = str(value)

            # NO aplicar compensaciones - usar resultados puros
            clean_result['adjusted_total_pnl'] = strategy_result.get('total_pnl', 0)
            clean_result['compensation_applied'] = 0.0
            clean_result['compensation_success_rate'] = 0.0
            clean_result['compensated_trades'] = 0

            dashboard_data['strategies'][strategy_name] = clean_result

            # Actualizar resumen
            pnl = strategy_result.get('total_pnl', 0)
            if pnl > dashboard_data['summary']['best_pnl']:
                dashboard_data['summary']['best_pnl'] = pnl
                dashboard_data['summary']['best_strategy'] = strategy_name

            dashboard_data['summary']['total_trades'] += strategy_result.get('total_trades', 0)

            win_rate = strategy_result.get('win_rate', 0)
            if win_rate > 0:
                win_rates.append(win_rate)

            # Agregar métricas de compensación
            dashboard_data['summary']['total_compensated_trades'] += strategy_result.get('compensated_trades', 0)
            dashboard_data['summary']['total_compensation_pnl'] += strategy_result.get('total_compensation_pnl', 0.0)

            comp_rate = strategy_result.get('compensation_success_rate', 0)
            if comp_rate > 0:
                compensation_rates.append(comp_rate)

        # Calcular promedios
        if win_rates:
            dashboard_data['summary']['avg_win_rate'] = sum(win_rates) / len(win_rates)

        if compensation_rates:
            dashboard_data['summary']['avg_compensation_rate'] = sum(compensation_rates) / len(compensation_rates)

        # Guardar archivo JSON
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Resultados guardados para dashboard: {results_file}")

    except Exception as e:
        logger.error(f"❌ Error guardando resultados para dashboard: {e}")

async def save_global_summary(all_results: dict, config, logger):
    """
    Guarda un resumen global de todos los símbolos para el dashboard
    """
    try:
        results_dir = Path("data/dashboard_results")
        summary_file = results_dir / "global_summary.json"

        global_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_symbols': len(all_results),
            'symbols': list(all_results.keys()),
            'config': {
                'timeframe': config.backtesting.timeframe,
                'start_date': config.backtesting.start_date,
                'end_date': config.backtesting.end_date,
                'initial_capital': config.backtesting.initial_capital
            },
            'metrics': {
                'total_pnl': 0.0,
                'total_trades': 0,
                'profitable_symbols': 0,
                'avg_win_rate': 0.0,
                'total_compensated_trades': 0,
                'total_compensation_pnl': 0.0,
                'avg_compensation_rate': 0.0
            }
        }

        win_rates = []
        compensation_rates = []

        for symbol, strategies in all_results.items():
            best_strategy = max(strategies.items(), key=lambda x: x[1].get('total_pnl', -10000))
            strategy_name, result = best_strategy

            pnl = result.get('total_pnl', 0)
            global_summary['metrics']['total_pnl'] += pnl
            global_summary['metrics']['total_trades'] += result.get('total_trades', 0)

            if pnl > 0:
                global_summary['metrics']['profitable_symbols'] += 1

            win_rate = result.get('win_rate', 0)
            if win_rate > 0:
                win_rates.append(win_rate)

            # Métricas de compensación
            global_summary['metrics']['total_compensated_trades'] += result.get('compensated_trades', 0)
            global_summary['metrics']['total_compensation_pnl'] += result.get('total_compensation_pnl', 0.0)

            comp_rate = result.get('compensation_success_rate', 0)
            if comp_rate > 0:
                compensation_rates.append(comp_rate)

        # Calcular promedios
        if win_rates:
            global_summary['metrics']['avg_win_rate'] = sum(win_rates) / len(win_rates)

        if compensation_rates:
            global_summary['metrics']['avg_compensation_rate'] = sum(compensation_rates) / len(compensation_rates)

        # Guardar resumen global
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(global_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Resumen global guardado: {summary_file}")

    except Exception as e:
        logger.error(f"❌ Error guardando resumen global: {e}")

if __name__ == "__main__":
    print("[INFO] Iniciando Bot Trader Copilot...")
    asyncio.run(main())
    print("[SUCCESS] Programa finalizado.")
