"""
Caché optimizado para mejorar rendimiento y reducir llamadas redundantes.
Implementa múltiples estrategias de caché según el tipo de datos.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Union, Tuple
import hashlib
import pickle
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import threading
from .interfaces import ICacheManager

@dataclass
class CacheEntry:
    """Entrada de caché con metadatos"""
    key: str
    data: Any
    created_at: datetime
    expires_at: Optional[datetime]
    size_bytes: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None

class InMemoryCache(ICacheManager):
    """Caché en memoria con TTL y límites de tamaño"""
    
    def __init__(self, max_size_mb: int = 100, default_ttl_minutes: int = 30):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché"""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            # Verificar expiración
            if entry.expires_at and datetime.now() > entry.expires_at:
                del self.cache[key]
                return None
            
            # Actualizar estadísticas de acceso
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            return entry.data
    
    def set(self, key: str, value: Any, ttl_minutes: Optional[int] = None) -> bool:
        """Almacena un valor en el caché"""
        with self.lock:
            try:
                # Calcular tamaño
                size_bytes = self._calculate_size(value)
                
                # Verificar si cabe en el caché
                if size_bytes > self.max_size_bytes:
                    self.logger.warning(f"Objeto demasiado grande para caché: {size_bytes} bytes")
                    return False
                
                # Limpiar espacio si es necesario
                self._ensure_space(size_bytes)
                
                # Crear entrada
                ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self.default_ttl
                expires_at = datetime.now() + ttl
                
                entry = CacheEntry(
                    key=key,
                    data=value,
                    created_at=datetime.now(),
                    expires_at=expires_at,
                    size_bytes=size_bytes
                )
                
                self.cache[key] = entry
                return True
                
            except Exception as e:
                self.logger.error(f"Error almacenando en caché: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """Elimina una entrada del caché"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Limpia todo el caché"""
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché"""
        with self.lock:
            total_size = sum(entry.size_bytes for entry in self.cache.values())
            total_entries = len(self.cache)
            
            if total_entries > 0:
                avg_size = total_size / total_entries
                total_accesses = sum(entry.access_count for entry in self.cache.values())
            else:
                avg_size = 0
                total_accesses = 0
            
            return {
                'total_entries': total_entries,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'usage_percent': (total_size / self.max_size_bytes) * 100,
                'average_entry_size': avg_size,
                'total_accesses': total_accesses
            }
    
    def _calculate_size(self, obj: Any) -> int:
        """Calcula el tamaño aproximado de un objeto"""
        try:
            if isinstance(obj, pd.DataFrame):
                return obj.memory_usage(deep=True).sum()
            elif isinstance(obj, (pd.Series, np.ndarray)):
                return obj.nbytes
            else:
                return len(pickle.dumps(obj))
        except Exception:
            # Estimación conservadora
            return 1024
    
    def _ensure_space(self, needed_bytes: int) -> None:
        """Asegura que hay espacio suficiente en el caché"""
        current_size = sum(entry.size_bytes for entry in self.cache.values())
        
        if current_size + needed_bytes <= self.max_size_bytes:
            return
        
        # Ordenar por LRU (menos recientemente usado)
        entries_by_lru = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at
        )
        
        # Eliminar entradas hasta tener espacio
        for key, entry in entries_by_lru:
            if current_size + needed_bytes <= self.max_size_bytes:
                break
            
            del self.cache[key]
            current_size -= entry.size_bytes
            self.logger.debug(f"Eliminada entrada de caché LRU: {key}")

class FileCache(ICacheManager):
    """Caché persistente en disco"""
    
    def __init__(self, cache_dir: str = "cache", max_size_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.metadata_file = self.cache_dir / "metadata.json"
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Cargar metadatos existentes
        self.metadata = self._load_metadata()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché de disco"""
        with self.lock:
            # Limpiar key para evitar problemas con caracteres especiales
            safe_key = key.replace('/', '_').replace('\\', '_').replace(':', '_')
            
            if safe_key not in self.metadata:
                return None
            
            entry_info = self.metadata[safe_key]
            
            # Verificar expiración
            if entry_info.get('expires_at'):
                expires_at = datetime.fromisoformat(entry_info['expires_at'])
                if datetime.now() > expires_at:
                    self._remove_entry(safe_key)
                    return None
            
            # Cargar datos
            try:
                file_path = self.cache_dir / f"{safe_key}.pkl"
                if not file_path.exists():
                    self._remove_entry(safe_key)
                    return None
                
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
                
                # Actualizar estadísticas
                entry_info['access_count'] = entry_info.get('access_count', 0) + 1
                entry_info['last_accessed'] = datetime.now().isoformat()
                self._save_metadata()
                
                return data
                
            except Exception as e:
                self.logger.error(f"Error cargando de caché: {e}")
                self._remove_entry(safe_key)
                return None
    
    def set(self, key: str, value: Any, ttl_minutes: Optional[int] = None) -> bool:
        """Almacena un valor en el caché de disco"""
        with self.lock:
            try:
                # Limpiar key para evitar problemas con caracteres especiales
                safe_key = key.replace('/', '_').replace('\\', '_').replace(':', '_')
                
                # Serializar datos
                file_path = self.cache_dir / f"{safe_key}.pkl"
                
                # Asegurar que el directorio padre existe
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
                
                # Calcular tamaño
                size_bytes = file_path.stat().st_size
                
                # Crear metadatos
                entry_info = {
                    'created_at': datetime.now().isoformat(),
                    'size_bytes': size_bytes,
                    'access_count': 0
                }
                
                if ttl_minutes:
                    expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
                    entry_info['expires_at'] = expires_at.isoformat()
                
                self.metadata[safe_key] = entry_info
                
                # Limpiar espacio si es necesario
                self._ensure_space()
                
                self._save_metadata()
                return True
                
            except Exception as e:
                self.logger.error(f"Error almacenando en caché de disco: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """Elimina una entrada del caché"""
        with self.lock:
            return self._remove_entry(key)
    
    def clear(self) -> None:
        """Limpia todo el caché"""
        with self.lock:
            for key in list(self.metadata.keys()):
                self._remove_entry(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché"""
        with self.lock:
            total_size = sum(entry.get('size_bytes', 0) for entry in self.metadata.values())
            total_entries = len(self.metadata)
            
            return {
                'total_entries': total_entries,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'max_size_mb': self.max_size_bytes / (1024 * 1024),
                'usage_percent': (total_size / self.max_size_bytes) * 100,
                'cache_directory': str(self.cache_dir)
            }
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Carga metadatos del disco"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Error cargando metadatos de caché: {e}")
        return {}
    
    def _save_metadata(self) -> None:
        """Guarda metadatos al disco"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error guardando metadatos de caché: {e}")
    
    def _remove_entry(self, key: str) -> bool:
        """Elimina una entrada completamente"""
        try:
            if key in self.metadata:
                del self.metadata[key]
            
            file_path = self.cache_dir / f"{key}.pkl"
            if file_path.exists():
                file_path.unlink()
            
            self._save_metadata()
            return True
        except Exception as e:
            self.logger.error(f"Error eliminando entrada de caché: {e}")
            return False
    
    def _ensure_space(self) -> None:
        """Asegura que hay espacio suficiente"""
        current_size = sum(entry.get('size_bytes', 0) for entry in self.metadata.values())
        
        if current_size <= self.max_size_bytes:
            return
        
        # Ordenar por LRU
        entries_by_lru = sorted(
            self.metadata.items(),
            key=lambda x: x[1].get('last_accessed', x[1].get('created_at', ''))
        )
        
        # Eliminar entradas hasta tener espacio
        for key, entry_info in entries_by_lru:
            if current_size <= self.max_size_bytes:
                break
            
            self._remove_entry(key)
            current_size -= entry_info.get('size_bytes', 0)

class SmartCacheManager:
    """Gestor de caché inteligente que combina memoria y disco"""
    
    def __init__(self, memory_cache_mb: int = 50, disk_cache_mb: int = 200):
        self.memory_cache = InMemoryCache(memory_cache_mb, default_ttl_minutes=15)
        self.file_cache = FileCache(max_size_mb=disk_cache_mb)
        self.logger = logging.getLogger(__name__)
    
    def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Obtiene un DataFrame con caché inteligente"""
        # Intentar memoria primero
        result = self.memory_cache.get(key)
        if result is not None:
            return result
        
        # Intentar disco
        result = self.file_cache.get(key)
        if result is not None:
            # Almacenar en memoria para acceso rápido
            self.memory_cache.set(key, result, ttl_minutes=10)
            return result
        
        return None
    
    def set_dataframe(self, key: str, df: pd.DataFrame, persist: bool = True) -> bool:
        """Almacena un DataFrame con estrategia inteligente"""
        # Siempre en memoria para acceso rápido
        memory_success = self.memory_cache.set(key, df, ttl_minutes=15)
        
        # En disco solo si se solicita persistencia
        disk_success = True
        if persist and len(df) > 100:  # Solo DataFrames grandes
            disk_success = self.file_cache.set(key, df, ttl_minutes=60)
        
        return memory_success or disk_success
    
    def get_cache_key(self, symbol: str, timeframe: str, start_date: str, end_date: str, 
                     indicators: bool = False) -> str:
        """Genera una clave de caché única"""
        key_parts = [symbol, timeframe, start_date, end_date]
        if indicators:
            key_parts.append("indicators")
        
        key_string = "_".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas combinadas"""
        memory_stats = self.memory_cache.get_stats()
        disk_stats = self.file_cache.get_stats()
        
        return {
            'memory_cache': memory_stats,
            'disk_cache': disk_stats,
            'total_entries': memory_stats['total_entries'] + disk_stats['total_entries']
        }
