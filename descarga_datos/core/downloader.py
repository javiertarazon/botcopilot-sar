#!/usr/bin/env python3
"""
Advanced Data Downloader - Sistema completo para descarga de datos
Soporta CCXT (criptomonedas) y MT5 (acciones) con paralelización,
manejo de errores, normalización y almacenamiento múltiple.
"""
import ccxt
import ccxt.async_support as ccxt_async
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os

from .mt5_downloader import MT5Downloader
from utils.storage import DataStorage, save_to_csv
from utils.normalization import DataNormalizer
from utils.technical_indicators_pipeline import calculate_technical_indicators, calculate_sar

class AdvancedDataDownloader:
    """
    Downloader avanzado que maneja múltiples fuentes de datos:
    - CCXT para criptomonedas (Bybit, Binance, etc.)
    - MT5 para acciones (AAPL.US, TSLA.US, etc.)
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Componentes
        self.ccxt_exchanges = {}
        # Compatibilidad: código legacy usa `self.exchanges`
        self.exchanges = self.ccxt_exchanges
        self.mt5_downloader = MT5Downloader(config.mt5) if hasattr(config, 'mt5') else None
        self.storage = DataStorage(f"{config.storage.path}/data.db")
        self.normalizer = DataNormalizer()

        # Configuración
        self.max_retries = getattr(config, 'max_retries', 3)
        self.retry_delay = getattr(config, 'retry_delay', 5)
        self.max_workers = 4  # Para paralelización

    async def initialize(self) -> bool:
        """Inicializa todas las conexiones"""
        try:
            # Inicializar CCXT exchanges
            ccxt_success = await self._setup_ccxt_exchanges()

            # Inicializar MT5
            mt5_success = self.mt5_downloader.initialize() if self.mt5_downloader else False

            if ccxt_success or mt5_success:
                self.logger.info("AdvancedDataDownloader inicializado correctamente")
                return True
            else:
                self.logger.error("No se pudo inicializar ningún downloader")
                return False

        except Exception as e:
            self.logger.error(f"Error en inicialización: {e}")
            return False

    async def _setup_ccxt_exchanges(self) -> bool:
        """Configura exchanges CCXT activos"""
        try:
            success_count = 0

            # Configurar Bybit
            if 'bybit' in self.config.exchanges and self.config.exchanges['bybit'].enabled:
                exchange_config = self.config.exchanges['bybit']
                self.ccxt_exchanges['bybit'] = ccxt_async.bybit({
                    'apiKey': exchange_config.api_key or '',
                    'secret': exchange_config.api_secret or '',
                    'sandbox': exchange_config.sandbox,
                    'timeout': exchange_config.timeout,
                })
                success_count += 1
                self.logger.info("Bybit configurado")

            # Configurar Binance
            if 'binance' in self.config.exchanges and self.config.exchanges['binance'].enabled:
                exchange_config = self.config.exchanges['binance']
                self.ccxt_exchanges['binance'] = ccxt_async.binance({
                    'apiKey': exchange_config.api_key or '',
                    'secret': exchange_config.api_secret or '',
                    'sandbox': exchange_config.sandbox,
                    'timeout': exchange_config.timeout,
                })
                success_count += 1
                self.logger.info("Binance configurado")

            # Configurar OKX
            if 'okx' in self.config.exchanges and self.config.exchanges['okx'].enabled:
                exchange_config = self.config.exchanges['okx']
                self.ccxt_exchanges['okx'] = ccxt_async.okx({
                    'apiKey': exchange_config.api_key or '',
                    'secret': exchange_config.api_secret or '',
                    'sandbox': exchange_config.sandbox,
                    'timeout': exchange_config.timeout,
                })
                success_count += 1
                self.logger.info("OKX configurado")

            return success_count > 0

        except Exception as e:
            self.logger.error(f"Error configurando CCXT: {e}")
            return False

    async def download_multiple_symbols(self, symbols: List[str], timeframe: str = "1h",
                                      start_date: str = None, end_date: str = None) -> Dict[str, pd.DataFrame]:
        """
        Descarga datos de múltiples símbolos en paralelo

        Args:
            symbols: Lista de símbolos
            timeframe: Timeframe para descarga
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)

        Returns:
            Diccionario símbolo -> DataFrame
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        self.logger.info(f"Descargando {len(symbols)} símbolos en paralelo...")

        # Crear tareas para paralelización
        tasks = []
        for symbol in symbols:
            task = self._download_symbol_with_retry(symbol, timeframe, start_date, end_date)
            tasks.append(task)

        # Ejecutar en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados
        symbol_data = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                self.logger.error(f"Error descargando {symbol}: {result}")
            elif result is not None:
                symbol_data[symbol] = result
                self.logger.info(f"✅ {symbol}: {len(result)} velas descargadas")

        return symbol_data

    async def _download_symbol_with_retry(self, symbol: str, timeframe: str,
                                        start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga un símbolo con manejo de errores y reintentos"""
        for attempt in range(self.max_retries):
            try:
                # Determinar si es cripto o acción
                if self._is_crypto_symbol(symbol):
                    return await self._download_crypto_symbol(symbol, timeframe, start_date, end_date)
                else:
                    return self._download_stock_symbol(symbol, timeframe, start_date, end_date)

            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Intento {attempt + 1} para {symbol} falló: {e}. Reintentando...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Todos los intentos fallaron para {symbol}: {e}")
                    return None

    def _is_crypto_symbol(self, symbol: str) -> bool:
        """Determina si un símbolo es de criptomoneda"""
        # Criptos tienen formato BASE/QUOTE (ej: BTC/USDT)
        return '/' in symbol

    async def _download_crypto_symbol(self, symbol: str, timeframe: str,
                                    start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga datos de criptomoneda desde CCXT"""
        if not self.ccxt_exchanges:
            raise Exception("No hay exchanges CCXT configurados")

        last_error: Optional[Exception] = None

        # Intentar en orden: exchange activo primero (si existe), luego el resto
        preferred = []
        if getattr(self.config, "active_exchange", None) in self.ccxt_exchanges:
            preferred.append(self.config.active_exchange)
        preferred.extend([name for name in self.ccxt_exchanges.keys() if name not in preferred])

        for exchange_name in preferred:
            exchange = self.ccxt_exchanges[exchange_name]
            try:
                since = int(pd.Timestamp(start_date).timestamp() * 1000)
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)

                if not ohlcv:
                    self.logger.warning(f"No se recibieron datos para {symbol} en {exchange_name}")
                    continue

                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

                end_dt = pd.Timestamp(end_date, tz="UTC")
                df = df[df["timestamp"] <= end_dt]
                return df

            except Exception as e:
                last_error = e
                self.logger.error(f"Error descargando {symbol} desde {exchange_name}: {e}")
                continue

        if last_error is not None:
            raise last_error
        return None

    def _download_stock_symbol(self, symbol: str, timeframe: str,
                             start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga datos de acciones desde MT5"""
        if not self.mt5_downloader or not self.mt5_downloader.connected:
            raise Exception("MT5 no está disponible")

        return self.mt5_downloader.download_symbol_data(symbol, timeframe, start_date, end_date)

    async def process_and_save_data(self, symbol_data: Dict[str, pd.DataFrame],
                                  timeframe: str, save_csv: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Procesa, normaliza y guarda los datos descargados

        Args:
            symbol_data: Diccionario símbolo -> DataFrame
            timeframe: Timeframe de los datos
            save_csv: Si guardar también en CSV

        Returns:
            Diccionario con los datos procesados (símbolo -> DataFrame normalizado)
        """
        processed_data = {}
        
        try:
            for symbol, df in symbol_data.items():
                if df is None or df.empty:
                    continue

                # Calcular indicadores técnicos
                df_with_indicators = self._calculate_technical_indicators(df)

                # Normalizar y escalar
                df_normalized = self._normalize_and_scale(df_with_indicators)

                # Guardar en SQLite (para uso del sistema)
                table_name = f"{symbol.replace('/', '_').replace('.', '_')}_{timeframe}"
                success_sql = self.storage.save_to_sqlite(df_normalized, table_name)

                # Guardar en CSV (para verificación visual)
                if save_csv and success_sql:
                    csv_path = f"{self.config.storage.path}/csv"
                    os.makedirs(csv_path, exist_ok=True)
                    csv_file = f"{csv_path}/{table_name}.csv"
                    success_csv = save_to_csv(df_normalized, csv_file)

                    if success_csv:
                        self.logger.info(f"✅ {symbol}: Datos guardados en SQLite y CSV")
                    else:
                        self.logger.warning(f"⚠️ {symbol}: Datos guardados en SQLite, error en CSV")

                # Almacenar datos procesados para devolver
                processed_data[symbol] = df_normalized

            return processed_data

        except Exception as e:
            self.logger.error(f"Error procesando datos: {e}")
            return False

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos completos"""
        try:
            return calculate_technical_indicators(df)

        except Exception as e:
            self.logger.error(f"Error calculando indicadores: {e}")
            return df

    def _calculate_sar(self, df: pd.DataFrame) -> pd.Series:
        """Calcula Parabolic SAR simplificado"""
        try:
            return calculate_sar(df)

        except Exception as e:
            self.logger.error(f"Error calculando SAR: {e}")
            return pd.Series([0.0] * len(df), index=df.index)

    def _normalize_and_scale(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza y escala los datos"""
        try:
            # Columnas que NO deben ser normalizadas (valores absolutos para estrategias)
            exclude_cols = [
                'open', 'high', 'low', 'close', 'volume',  # Precios y volumen
                'atr', 'adx', 'sar', 'rsi', 'macd', 'macd_signal',  # Indicadores técnicos
                'bb_upper', 'bb_lower',  # Bandas de Bollinger
                'ema_10', 'ema_20', 'ema_200'  # EMAs necesarias para estrategias
            ]

            # Identificar columnas numéricas (excluir timestamp y columnas excluidas)
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            numeric_cols = [col for col in numeric_cols if col not in exclude_cols and col != 'timestamp']

            if not numeric_cols:
                return df

            # Normalizar solo columnas que no afectan las estrategias
            df_normalized = df.copy()
            for col in numeric_cols:
                # Min-Max scaling solo para columnas permitidas
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val > min_val:
                    df_normalized[col] = (df[col] - min_val) / (max_val - min_val)

            return df_normalized

        except Exception as e:
            self.logger.error(f"Error en normalización: {e}")
            return df

    async def get_data_from_db(self, symbol: str, timeframe: str,
                             start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """
        Obtiene datos desde la base de datos SQLite

        Args:
            symbol: Símbolo
            timeframe: Timeframe
            start_date: Fecha inicio (opcional)
            end_date: Fecha fin (opcional)

        Returns:
            DataFrame con datos o None
        """
        try:
            table_name = f"{symbol.replace('/', '_').replace('.', '_')}_{timeframe}"

            # Query para obtener datos
            query = f"SELECT * FROM {table_name}"

            # Aquí iría la lógica para ejecutar la query
            # Por ahora retornamos None para indicar que no está implementado
            self.logger.warning(f"get_data_from_db no implementado aún para {table_name}")
            return None

        except Exception as e:
            self.logger.error(f"Error obteniendo datos de DB: {e}")
            return None

    async def shutdown(self):
        """Cierra todas las conexiones"""
        try:
            # Cerrar exchanges CCXT
            for exchange_name, exchange in list(self.ccxt_exchanges.items()):
                try:
                    await exchange.close()
                except Exception as e:
                    self.logger.warning(f"Error cerrando exchange {exchange_name}: {e}")

            # Cerrar MT5
            if self.mt5_downloader:
                self.mt5_downloader.shutdown()

            self.ccxt_exchanges.clear()
            self.logger.info("AdvancedDataDownloader cerrado correctamente")

        except Exception as e:
            self.logger.error(f"Error en shutdown: {e}")

    async def async_download_ohlcv(self, symbol: str, exchange_name: str,
                                 timeframe: str = '1h', limit: int = 1000) -> tuple:
        """
        Descarga datos OHLCV de un exchange
        """
        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange {exchange_name} no configurado")

        exchange = self.exchanges[exchange_name]

        try:
            # Descargar datos
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            if not ohlcv:
                return None, {"error": "No data received"}

            # Convertir a DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            # No establecer timestamp como índice para mantenerlo como columna
            # df.set_index('timestamp', inplace=True)

            # Convertir tipos de datos
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            stats = {
                'exchange': exchange_name,
                'symbol': symbol,
                'timeframe': timeframe,
                'records': len(df),
                'start_date': df.index.min(),
                'end_date': df.index.max()
            }

            return df, stats

        except Exception as e:
            self.logger.error(f"[ERROR] Error descargando {symbol} desde {exchange_name}: {e}")
            return None, {"error": str(e)}

    async def close_exchanges(self):
        """Cierra todas las conexiones de exchanges"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                self.logger.info(f"[INFO] Exchange {exchange_name} cerrado")
            except Exception as e:
                self.logger.error(f"[ERROR] Error cerrando {exchange_name}: {e}")

        self.exchanges.clear()
