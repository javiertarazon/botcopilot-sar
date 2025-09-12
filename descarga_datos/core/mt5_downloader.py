#!/usr/bin/env python3
"""
MT5 Data Downloader - Descarga datos de acciones desde MetaTrader 5
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
import asyncio

# Intentar importar MT5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logging.warning("MetaTrader5 no disponible - solo se usarán datos de CCXT")

class MT5Downloader:
    """Downloader para datos de acciones desde MT5"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.connected = False
        self.max_retries = getattr(config, 'max_retries', 3) if hasattr(config, 'max_retries') else 3
        self.retry_delay = getattr(config, 'retry_delay', 5) if hasattr(config, 'retry_delay') else 5

    def initialize(self) -> bool:
        """Inicializa la conexión con MT5"""
        if not MT5_AVAILABLE:
            self.logger.warning("MT5 no disponible")
            return False

        try:
            if not mt5.initialize():
                self.logger.error(f"Error al inicializar MT5: {mt5.last_error()}")
                return False

            # Login si se proporcionan credenciales
            if hasattr(self.config, 'mt5') and self.config.mt5.login:
                if not mt5.login(
                    self.config.mt5.login,
                    password=self.config.mt5.password,
                    server=self.config.mt5.server
                ):
                    self.logger.error(f"Error en login MT5: {mt5.last_error()}")
                    return False

            self.connected = True
            self.logger.info("MT5 conectado correctamente")
            return True

        except Exception as e:
            self.logger.error(f"Error inicializando MT5: {e}")
            return False

    def shutdown(self):
        """Cierra la conexión con MT5"""
        if MT5_AVAILABLE and self.connected:
            mt5.shutdown()
            self.connected = False
            self.logger.info("MT5 desconectado")

    def _retry_operation(self, operation, *args, **kwargs):
        """Ejecuta una operación con reintentos"""
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Intento {attempt + 1} falló: {e}. Reintentando en {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Todos los intentos fallaron: {e}")
                    raise e

    def download_symbol_data(self, symbol: str, timeframe: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Descarga datos históricos de un símbolo desde MT5

        Args:
            symbol: Símbolo (ej: "AAPL.US", "TSLA.US")
            timeframe: Timeframe (ej: "1h", "1d")
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD)

        Returns:
            DataFrame con datos OHLCV o None si falla
        """
        if not self.connected:
            self.logger.error("MT5 no está conectado")
            return None

        try:
            # Convertir timeframe a MT5
            mt5_timeframe = self._convert_timeframe(timeframe)
            if mt5_timeframe is None:
                self.logger.error(f"Timeframe no soportado: {timeframe}")
                return None

            # Convertir fechas
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Descargar datos con reintentos
            rates = self._retry_operation(
                mt5.copy_rates_range,
                symbol,
                mt5_timeframe,
                start_dt,
                end_dt
            )

            if rates is None or len(rates) == 0:
                self.logger.warning(f"No se encontraron datos para {symbol}")
                return None

            # Convertir a DataFrame
            df = pd.DataFrame(rates)
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')

            # Renombrar columnas para consistencia
            df = df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'tick_volume': 'volume'
            })

            # Mantener solo columnas necesarias
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

            self.logger.info(f"Datos descargados: {symbol} - {len(df)} velas")
            return df

        except Exception as e:
            self.logger.error(f"Error descargando {symbol}: {e}")
            return None

    def _convert_timeframe(self, timeframe: str) -> Optional[int]:
        """Convierte timeframe string a constante MT5"""
        if not MT5_AVAILABLE:
            return None

        mapping = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1,
            '1w': mt5.TIMEFRAME_W1,
            '1M': mt5.TIMEFRAME_MN1
        }
        return mapping.get(timeframe)

    def get_available_symbols(self) -> List[str]:
        """Obtiene lista de símbolos disponibles"""
        if not self.connected:
            return []

        try:
            symbols = mt5.symbols_get()
            return [s.name for s in symbols] if symbols else []
        except Exception as e:
            self.logger.error(f"Error obteniendo símbolos: {e}")
            return []

    def close(self):
        """Alias para shutdown() para compatibilidad"""
        self.shutdown()
