"""
ALTERNATIVA 1: ESTRATEGIA ADAPTATIVA CON MACHINE LEARNING
========================================================

Estrategia que aprende de los datos históricos para optimizar parámetros dinámicamente.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

@dataclass
class AdaptiveStrategyConfig:
    """Configuración para estrategia adaptativa"""
    learning_window: int = 1000  # Barras para entrenamiento
    adaptation_frequency: int = 100  # Cada cuántas barras se reentrena
    min_samples_split: int = 50
    max_depth: int = 10
    feature_importance_threshold: float = 0.05

    # Parámetros dinámicos (se ajustan automáticamente)
    sensitivity_range: Tuple[int, int] = (1, 5)
    atr_period_range: Tuple[int, int] = (5, 20)
    risk_percent_range: Tuple[float, float] = (0.5, 3.0)

class MLAdaptiveUTBotStrategy:
    """
    Estrategia UT Bot + PSAR con aprendizaje automático

    Características:
    - Parámetros dinámicos basados en ML
    - Aprendizaje continuo del mercado
    - Adaptación automática a condiciones cambiantes
    - Feature engineering avanzado
    """

    def __init__(self, config: AdaptiveStrategyConfig = None):
        self.config = config or AdaptiveStrategyConfig()
        self.model = None
        self.feature_columns = []
        self.performance_history = []
        self.market_regime = "unknown"

        # Parámetros dinámicos actuales
        self.current_sensitivity = 2
        self.current_atr_period = 14
        self.current_risk_percent = 1.5

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extrae características avanzadas para ML"""
        # Trabajar con una copia para no modificar el DataFrame original
        data = df.copy()
        
        # Asegurarse de que la columna 'returns' exista o calcularla
        if 'returns' not in data.columns:
            data['returns'] = data['close'].pct_change()

        features = pd.DataFrame(index=data.index)

        # Características básicas
        features['returns'] = data['returns']
        features['volatility'] = data['returns'].rolling(20).std()
        
        # Manejar posible ausencia de 'volume'
        if 'volume' in data.columns:
            features['volume_ratio'] = data['volume'] / data['volume'].rolling(20).mean()
        else:
            features['volume_ratio'] = 0 # O un valor neutral

        # Características técnicas
        features['rsi'] = self.calculate_rsi(data['close'])
        features['macd_signal'] = self.calculate_macd_signal(data['close'])
        features['bb_position'] = self.calculate_bb_position(data['close'])

        # Características de momentum
        features['momentum_10'] = data['close'] / data['close'].shift(10) - 1
        features['momentum_20'] = data['close'] / data['close'].shift(20) - 1

        # Características de volumen
        features['volume_trend'] = data['volume'].rolling(10).mean() / data['volume'].rolling(20).mean()

        return features

    def train_model(self, historical_data: pd.DataFrame):
        """Entrena el modelo de ML con datos históricos"""
        try:
            # Extraer características
            features = self.extract_features(historical_data)

            # Crear etiquetas (1 si el trade siguiente es profitable, 0 si no)
            future_returns = historical_data['close'].shift(-5) / historical_data['close'] - 1
            labels = (future_returns > 0.005).astype(int)  # 0.5% como umbral
            labels = pd.Series(labels, name='target')  # Crear Series con nombre

            # Limpiar datos
            valid_data = pd.concat([features, labels], axis=1).dropna()
            
            if len(valid_data) < 50:  # Reducir el umbral mínimo
                print(f"⚠️ Datos insuficientes para entrenar modelo: {len(valid_data)} filas")
                return False
            
            X = valid_data[features.columns]
            y = valid_data['target']

            if len(X) < 10 or len(y) < 10:
                print("⚠️ Datos insuficientes después de limpieza")
                return False

            # Entrenar modelo
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                random_state=42
            )

            self.model.fit(X_train, y_train)

            # Evaluar modelo
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Guardar importancia de características
            feature_importance = pd.Series(
                self.model.feature_importances_,
                index=X.columns
            ).sort_values(ascending=False)

            # Filtrar características importantes
            self.feature_columns = feature_importance[
                feature_importance > self.config.feature_importance_threshold
            ].index.tolist()

            print(f"✅ Modelo entrenado con accuracy: {accuracy:.2f}")
            return accuracy > 0.55  # Umbral mínimo de accuracy

        except Exception as e:
            print(f"❌ Error entrenando modelo: {e}")
            return False

    def adapt_parameters(self, current_data: pd.DataFrame):
        """Adapta parámetros basados en condiciones actuales del mercado"""
        if self.model is None:
            return

        # Extraer características actuales
        features = self.extract_features(current_data).tail(1)[self.feature_columns]

        if len(features) == 0:
            return

        # Predecir calidad de la señal
        signal_quality = self.model.predict_proba(features)[0][1]

        # Adaptar parámetros basados en calidad de señal y régimen de mercado
        if signal_quality > 0.7:  # Alta calidad
            self.current_sensitivity = min(4, self.current_sensitivity + 0.5)
            self.current_risk_percent = min(2.5, self.current_risk_percent + 0.2)
        elif signal_quality < 0.4:  # Baja calidad
            self.current_sensitivity = max(1, self.current_sensitivity - 0.5)
            self.current_risk_percent = max(0.8, self.current_risk_percent - 0.2)

        # Adaptar basado en volatilidad
        current_volatility = features['volatility'].iloc[0]
        if current_volatility > features['volatility'].quantile(0.8):
            self.current_atr_period = min(25, self.current_atr_period + 2)
        elif current_volatility < features['volatility'].quantile(0.2):
            self.current_atr_period = max(8, self.current_atr_period - 2)

    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula señales con parámetros adaptativos"""
        # Usar parámetros actuales para calcular señales UT Bot
        df = df.copy()

        # Calcular indicadores con parámetros adaptativos
        df['atr'] = self.calculate_atr(df, self.current_atr_period)
        df['n_loss'] = self.current_sensitivity * df['atr']

        # Calcular trailing stop adaptativo
        df['trailing_stop'] = self.calculate_adaptive_trailing_stop(df)

        # Calcular señales
        df['ema_val'] = df['close']
        df['above'] = (df['ema_val'] > df['trailing_stop']) & (df['ema_val'].shift(1) <= df['trailing_stop'].shift(1))
        df['below'] = (df['ema_val'] < df['trailing_stop']) & (df['ema_val'].shift(1) >= df['trailing_stop'].shift(1))

        df['buy_signal'] = (df['close'] > df['trailing_stop']) & df['above']
        df['sell_signal'] = (df['close'] < df['trailing_stop']) & df['below']

        return df

    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula ATR"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def calculate_adaptive_trailing_stop(self, df: pd.DataFrame) -> pd.Series:
        """Calcula trailing stop adaptativo basado en volatilidad"""
        trailing_stop = pd.Series(index=df.index, dtype=float)

        for i in range(len(df)):
            price = df['close'].iloc[i]
            n_loss = df['n_loss'].iloc[i]

            if i == 0:
                trailing_stop.iloc[i] = price - n_loss
                continue

            prev_stop = trailing_stop.iloc[i-1]

            # Lógica adaptativa del trailing stop
            if price > prev_stop:
                trailing_stop.iloc[i] = max(prev_stop, price - n_loss)
            else:
                trailing_stop.iloc[i] = price + n_loss

        return trailing_stop

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd_signal(self, prices: pd.Series) -> pd.Series:
        """Calcula señal MACD"""
        exp1 = prices.ewm(span=12).mean()
        exp2 = prices.ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()
        return macd - signal

    def calculate_bb_position(self, prices: pd.Series) -> pd.Series:
        """Calcula posición en Bollinger Bands"""
        sma = prices.rolling(20).mean()
        std = prices.rolling(20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return (prices - lower) / (upper - lower)

    def run_backtest(self, data: pd.DataFrame, symbol: str) -> Dict:
        """Ejecuta backtest con adaptación automática"""
        results = {
            'total_trades': 0,
            'winning_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'adaptation_events': 0
        }

        # Entrenar modelo inicial
        if len(data) > self.config.learning_window:
            training_data = data.iloc[:self.config.learning_window]
            if self.train_model(training_data):
                print(f"✅ Modelo inicial entrenado para {symbol}")

        capital = 10000.0
        position = 0
        trades = []
        adaptation_count = 0

        for i in range(self.config.learning_window, len(data), self.config.adaptation_frequency):
            # Adaptar parámetros cada N barras
            current_window = data.iloc[max(0, i-self.config.learning_window):i]
            self.adapt_parameters(current_window)
            adaptation_count += 1

            # Calcular señales con parámetros adaptativos
            signals_window = data.iloc[i:i+self.config.adaptation_frequency]
            if len(signals_window) > 0:
                signals_df = self.calculate_signals(signals_window)

                # Ejecutar trades (lógica simplificada)
                for j, row in signals_df.iterrows():
                    if row['buy_signal'] and position == 0:
                        position = 1
                        entry_price = row['close']
                    elif row['sell_signal'] and position == 1:
                        exit_price = row['close']
                        pnl = (exit_price - entry_price) * (capital * self.current_risk_percent / 100) / entry_price
                        capital += pnl
                        trades.append({'pnl': pnl})
                        position = 0

        # Calcular métricas
        if trades:
            results['total_trades'] = len(trades)
            results['winning_trades'] = len([t for t in trades if t['pnl'] > 0])
            results['win_rate'] = results['winning_trades'] / results['total_trades']
            results['total_pnl'] = sum(t['pnl'] for t in trades)
            results['adaptation_events'] = adaptation_count

        return results
