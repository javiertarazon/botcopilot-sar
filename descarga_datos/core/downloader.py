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
from .unified_storage import UnifiedDataStorage
# from utils.normalization import DataNormalizer  # Comentado - módulo no existe

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
        from .interfaces import create_storage_config
        storage_config = create_storage_config()  # Siempre usar la función que incluye enable_sqlite
        self.storage = UnifiedDataStorage(storage_config)
        # self.normalizer = DataNormalizer()  # Comentado - módulo no existe

        # Inicializar atributos que se usan en initialize()
        self.ccxt_exchanges = {}
        self.exchanges = self.ccxt_exchanges  # Alias para compatibilidad
        self.mt5_downloader = MT5Downloader(config.mt5) if hasattr(config, 'mt5') and config.mt5 else None

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

            # Configurar Kraken
            if 'kraken' in self.config.exchanges and self.config.exchanges['kraken'].enabled:
                exchange_config = self.config.exchanges['kraken']
                self.ccxt_exchanges['kraken'] = ccxt_async.kraken({
                    'apiKey': exchange_config.api_key or '',
                    'secret': exchange_config.api_secret or '',
                    'sandbox': exchange_config.sandbox,
                    'timeout': exchange_config.timeout,
                })
                success_count += 1
                self.logger.info("Kraken configurado")

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

        # Usar el exchange activo configurado
        active_exchange = getattr(self.config, 'active_exchange', 'binance')
        if active_exchange in self.ccxt_exchanges:
            exchange_name = active_exchange
            exchange = self.ccxt_exchanges[exchange_name]
        else:
            # Fallback al primer exchange disponible
            exchange_name = list(self.ccxt_exchanges.keys())[0]
            exchange = self.ccxt_exchanges[exchange_name]

        try:
            # Convertir fechas
            since = int(pd.Timestamp(start_date).timestamp() * 1000)

            # Descargar datos
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)

            if not ohlcv:
                return None

            # Convertir a DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Filtrar por fecha fin
            end_dt = pd.Timestamp(end_date)
            df = df[df['timestamp'] <= end_dt]

            return df

        except Exception as e:
            self.logger.error(f"Error descargando {symbol} desde {exchange_name}: {e}")
            raise e

    def _download_stock_symbol(self, symbol: str, timeframe: str,
                             start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Descarga datos de acciones desde MT5"""
        if not self.mt5_downloader or not self.mt5_downloader.connected:
            raise Exception("MT5 no está disponible")

        return self.mt5_downloader.download_symbol_data(symbol, timeframe, start_date, end_date)

    async def process_and_save_data(self, symbol_data: Dict[str, pd.DataFrame], 
                                  timeframe: str, save_csv: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Procesa y guarda los datos descargados
        
        Args:
            symbol_data: Diccionario símbolo -> DataFrame
            timeframe: Timeframe de los datos
            save_csv: Si guardar en CSV además de SQLite
            
        Returns:
            Diccionario con datos procesados
        """
        processed_data = {}
        
        for symbol, df in symbol_data.items():
            try:
                self.logger.info(f"Procesando datos para {symbol}...")
                
                # Procesar/normalizar datos si es necesario
                df_processed = self._normalize_data(df.copy())
                
                # Crear objeto OHLCVData para el storage
                from .interfaces import OHLCVData
                ohlcv_data = OHLCVData(df_processed)
                
                # Guardar en storage
                success = self.storage.save_ohlcv_data(symbol, timeframe, ohlcv_data)
                
                if success:
                    processed_data[symbol] = df_processed
                    self.logger.info(f"✅ Datos procesados y guardados para {symbol}")
                else:
                    self.logger.error(f"❌ Error guardando datos para {symbol}")
                    
            except Exception as e:
                self.logger.error(f"Error procesando {symbol}: {e}")
                
        return processed_data

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos completos"""
        try:
            # Copia del DataFrame
            result_df = df.copy()

            # ATR (Average True Range)
            high_low = result_df['high'] - result_df['low']
            high_close = np.abs(result_df['high'] - result_df['close'].shift(1))
            low_close = np.abs(result_df['low'] - result_df['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            result_df['atr'] = tr.ewm(span=14, adjust=False).mean()

            # ADX (Average Directional Index)
            high_diff = result_df['high'].diff()
            low_diff = result_df['low'].diff()
            plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
            minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
            atr_val = result_df['atr']
            plus_di = 100 * (pd.Series(plus_dm).ewm(span=14, adjust=False).mean() / atr_val)
            minus_di = 100 * (pd.Series(minus_dm).ewm(span=14, adjust=False).mean() / atr_val)
            dx = 100 * np.abs((plus_di - minus_di) / ((plus_di + minus_di) + 1e-9))
            result_df['adx'] = dx.ewm(span=14, adjust=False).mean()

            # SAR (Parabolic SAR) - Implementación simplificada
            result_df['sar'] = self._calculate_sar(result_df)

            # RSI
            delta = result_df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            result_df['rsi'] = 100 - (100 / (1 + rs))

            # MACD
            ema_12 = result_df['close'].ewm(span=12, adjust=False).mean()
            ema_26 = result_df['close'].ewm(span=26, adjust=False).mean()
            result_df['macd'] = ema_12 - ema_26
            result_df['macd_signal'] = result_df['macd'].ewm(span=9, adjust=False).mean()

            # EMAs necesarias para las estrategias UT Bot
            result_df['ema_10'] = result_df['close'].ewm(span=10, adjust=False).mean()
            result_df['ema_20'] = result_df['close'].ewm(span=20, adjust=False).mean()
            result_df['ema_200'] = result_df['close'].ewm(span=200, adjust=False).mean()

            # Bollinger Bands
            sma_20 = result_df['close'].rolling(window=20).mean()
            std_20 = result_df['close'].rolling(window=20).std()
            result_df['bb_upper'] = sma_20 + (std_20 * 2)
            result_df['bb_lower'] = sma_20 - (std_20 * 2)

            # Llenar NaN con 0
            result_df = result_df.fillna(0)

            return result_df

        except Exception as e:
            self.logger.error(f"Error calculando indicadores: {e}")
            return df

    def _calculate_sar(self, df: pd.DataFrame) -> pd.Series:
        """Calcula Parabolic SAR simplificado"""
        try:
            length = len(df)
            sar = np.zeros(length)
            high = df['high'].values
            low = df['low'].values

            if length > 0:
                sar[0] = low[0]  # Comenzar con el primer low

            # Parámetros SAR
            acceleration = 0.02
            max_acceleration = 0.2

            # Variables de estado
            trend = 1  # 1 = uptrend, -1 = downtrend
            extreme_point = high[0] if trend == 1 else low[0]
            acceleration_factor = acceleration

            for i in range(1, length):
                # Calcular nuevo SAR
                sar[i] = sar[i-1] + acceleration_factor * (extreme_point - sar[i-1])

                # Determinar cambio de tendencia
                if trend == 1:  # Uptrend
                    if low[i] <= sar[i]:
                        trend = -1
                        sar[i] = extreme_point
                        extreme_point = low[i]
                        acceleration_factor = acceleration
                    else:
                        if high[i] > extreme_point:
                            extreme_point = high[i]
                            acceleration_factor = min(acceleration_factor + acceleration, max_acceleration)
                        sar[i] = min(sar[i], low[i-1], low[i])
                else:  # Downtrend
                    if high[i] >= sar[i]:
                        trend = 1
                        sar[i] = extreme_point
                        extreme_point = high[i]
                        acceleration_factor = acceleration
                    else:
                        if low[i] < extreme_point:
                            extreme_point = low[i]
                            acceleration_factor = min(acceleration_factor + acceleration, max_acceleration)
                        sar[i] = max(sar[i], high[i-1], high[i])

            return pd.Series(sar, index=df.index)

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
            for exchange_name, exchange in self.ccxt_exchanges.items():
                try:
                    await exchange.close()
                    self.logger.info(f"Exchange {exchange_name} cerrado correctamente")
                except Exception as e:
                    self.logger.warning(f"Error cerrando exchange {exchange_name}: {e}")

            # Cerrar MT5
            if self.mt5_downloader:
                self.mt5_downloader.close()

            self.logger.info("AdvancedDataDownloader cerrado correctamente")

        except Exception as e:
            self.logger.error(f"Error en shutdown: {e}")

    def close(self):
        """Alias para shutdown() para compatibilidad"""
        # Como shutdown es async, creamos una versión sync que ejecuta el shutdown
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si hay un loop corriendo, programamos el shutdown
                asyncio.create_task(self.shutdown())
            else:
                # Si no hay loop, ejecutamos directamente
                loop.run_until_complete(self.shutdown())
        except Exception as e:
            self.logger.error(f"Error en close(): {e}")

        except Exception as e:
            self.logger.error(f"[ERROR] Error configurando exchanges: {e}")
            return False

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

    def _normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza y limpia los datos OHLCV descargados.

        Args:
            df (pd.DataFrame): DataFrame con datos crudos

        Returns:
            pd.DataFrame: DataFrame normalizado y limpio
        """
        try:
            # Crear una copia para no modificar el original
            df_clean = df.copy()

            # Asegurar que timestamp esté en el formato correcto
            if 'timestamp' in df_clean.columns:
                df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'])
                # Ordenar por timestamp
                df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)

            # Limpiar valores nulos en columnas OHLCV
            ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in ohlcv_cols:
                if col in df_clean.columns:
                    # Reemplazar valores nulos con el último valor válido (forward fill)
                    df_clean[col] = df_clean[col].ffill()
                    # Si aún quedan nulos al inicio, usar backward fill
                    df_clean[col] = df_clean[col].bfill()
                    # Convertir a tipos numéricos
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

            # Eliminar filas que aún tengan valores nulos en OHLC
            essential_cols = ['open', 'high', 'low', 'close']
            existing_essential = [col for col in essential_cols if col in df_clean.columns]
            if existing_essential:
                df_clean = df_clean.dropna(subset=existing_essential)

            # Asegurar que high >= max(open, close) y low <= min(open, close)
            if all(col in df_clean.columns for col in ['open', 'high', 'low', 'close']):
                # Corregir high si es menor que max(open, close)
                df_clean['high'] = df_clean[['high', 'open', 'close']].max(axis=1)
                # Corregir low si es mayor que min(open, close)
                df_clean['low'] = df_clean[['low', 'open', 'close']].min(axis=1)

            # Eliminar duplicados basados en timestamp
            if 'timestamp' in df_clean.columns:
                df_clean = df_clean.drop_duplicates(subset=['timestamp'], keep='first')

            # Resetear índice
            df_clean = df_clean.reset_index(drop=True)

            # Calcular indicadores técnicos después de la normalización
            df_clean = self._calculate_technical_indicators(df_clean)

            self.logger.debug(f"Datos normalizados con indicadores: {len(df_clean)} filas, columnas: {list(df_clean.columns)}")

            return df_clean

        except Exception as e:
            self.logger.error(f"Error en normalización de datos: {e}")
            return df  # Retornar datos originales si falla la normalización

    async def close_exchanges(self):
        """Cierra todas las conexiones de exchanges"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                self.logger.info(f"[INFO] Exchange {exchange_name} cerrado")
            except Exception as e:
                self.logger.error(f"[ERROR] Error cerrando {exchange_name}: {e}")

        self.exchanges.clear()