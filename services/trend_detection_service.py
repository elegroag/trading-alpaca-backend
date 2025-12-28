from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from services.alpaca_service import alpaca_service, AlpacaServiceException
from services.fair_value_service import fair_value_service, FairValueServiceException
from models.user import User


FEATURE_COLUMNS = [
    "EMA20",
    "EMA50",
    "MACD",
    "MACD_signal",
    "RSI",
    "ATR",
    "EMA_spread",
]

TREND_FUTURE_DAYS = 3
TREND_UP_THRESHOLD = 0.01
TREND_DOWN_THRESHOLD = -0.01


class TrendDetectionServiceException(Exception):
    pass


class TrendDetectionService:
    def _build_df_from_bars(
        self,
        symbol: str,
        limit: int = 200,
        user: Optional[User] = None,
    ) -> pd.DataFrame:
        bars = alpaca_service.get_bars(symbol, timeframe="1D", limit=limit, user=user)
        if not bars:
            raise TrendDetectionServiceException(
                f"No se encontraron barras históricas para el símbolo {symbol}"
            )

        df = pd.DataFrame(bars)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").set_index("timestamp")
        else:
            df = df.sort_index()

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df["EMA20"] = EMAIndicator(df["close"], window=20).ema_indicator()
        df["EMA50"] = EMAIndicator(df["close"], window=50).ema_indicator()

        macd = MACD(df["close"])
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()

        df["RSI"] = RSIIndicator(df["close"], window=14).rsi()

        df["ATR"] = AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()

        df["EMA_spread"] = df["EMA20"] - df["EMA50"]

        df = df.dropna()
        return df

    def _create_target(
        self,
        df: pd.DataFrame,
        future_days: int = TREND_FUTURE_DAYS,
        up_threshold: float = TREND_UP_THRESHOLD,
        down_threshold: float = TREND_DOWN_THRESHOLD,
    ) -> pd.DataFrame:
        df = df.copy()

        df["future_close"] = df["close"].shift(-future_days)
        df["pct_change"] = (df["future_close"] - df["close"]) / df["close"]

        df["trend"] = 0
        df.loc[df["pct_change"] > up_threshold, "trend"] = 1
        df.loc[df["pct_change"] < down_threshold, "trend"] = -1

        df = df.dropna()
        return df

    def _train_model(self, df: pd.DataFrame, model_type: str = "xgboost") -> Dict[str, Any]:
        X = df[FEATURE_COLUMNS]
        # Mapear clases: -1 -> 0, 0 -> 1, 1 -> 2
        y = df["trend"] + 1

        if len(df) < 50:
            raise TrendDetectionServiceException(
                "No hay suficientes muestras históricas para entrenar el modelo"
            )

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            shuffle=False,
        )

        # Verificar clases presentes en el conjunto de entrenamiento
        train_unique = np.sort(y_train.unique())
        n_classes_train = len(train_unique)
        if n_classes_train < 2:
            raise TrendDetectionServiceException(
                "No hay suficiente variación en los datos para entrenar el modelo"
            )

        model_type_key = (model_type or "xgboost").lower()

        # Random Forest: usa y directamente (0,1,2)
        if model_type_key in {"rf", "random_forest", "random-forest"}:
            model = RandomForestClassifier(
                n_estimators=100,  # Reducido de 300 a 100
                max_depth=5,       # Reducido de 8 a 5
                n_jobs=1,          # Cambiado de -1 a 1 para evitar multiprocessing
                class_weight="balanced_subsample",
                random_state=42,   # Para reproducibilidad
            )
            model_type_key = "random_forest"

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            # Reporte sobre tendencias (-1,0,1) para consistencia
            y_test_trend = y_test - 1
            y_pred_trend = y_pred - 1
            report_str = classification_report(
                y_test_trend,
                y_pred_trend,
                labels=[-1, 0, 1],
                zero_division=0,
            )

            return {
                "model": model,
                "label_encoder": None,
                "report": report_str,
                "n_samples": int(len(df)),
                "model_type": model_type_key,
            }

        # XGBoost: asegurar clases consecutivas desde 0 según lo que realmente aparece en y_train
        from sklearn.preprocessing import LabelEncoder

        label_encoder = LabelEncoder()
        label_encoder.fit(y_train)
        y_train_encoded = label_encoder.transform(y_train)

        n_classes_enc = len(label_encoder.classes_)

        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="multi:softprob" if n_classes_enc > 2 else "binary:logistic",
            eval_metric="mlogloss" if n_classes_enc > 2 else "logloss",
            num_class=n_classes_enc if n_classes_enc > 2 else None,
        )
        model_type_key = "xgboost"

        model.fit(X_train, y_train_encoded)

        # Reporte: puede fallar si y_test contiene clases no vistas en entrenamiento
        try:
            y_test_encoded = label_encoder.transform(y_test)
            y_pred_encoded = model.predict(X_test)

            y_test_original = label_encoder.inverse_transform(y_test_encoded) - 1
            y_pred_original = label_encoder.inverse_transform(y_pred_encoded) - 1

            report_str = classification_report(
                y_test_original,
                y_pred_original,
                labels=[-1, 0, 1],
                zero_division=0,
            )
        except ValueError:
            report_str = (
                "No se pudo generar reporte de clasificación porque el conjunto de "
                "prueba contiene clases no vistas en el entrenamiento."
            )

        return {
            "model": model,
            "label_encoder": label_encoder,
            "report": report_str,
            "n_samples": int(len(df)),
            "model_type": model_type_key,
        }

    def analyze_symbol(
        self,
        symbol: str,
        user: Optional[User] = None,
        limit: int = 200,
        profile: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            df_raw = self._build_df_from_bars(symbol, limit=limit, user=user)
        except AlpacaServiceException as e:
            raise TrendDetectionServiceException(str(e))

        df_ind = self._add_indicators(df_raw)
        if df_ind.empty:
            raise TrendDetectionServiceException(
                "No fue posible calcular indicadores técnicos para el símbolo"
            )

        profile_key = (profile or "corto").lower()
        if profile_key == "intradia":
            future_days = 1
            up_threshold = 0.003
            down_threshold = -0.003
        elif profile_key == "largo":
            future_days = 10
            up_threshold = 0.03
            down_threshold = -0.03
        else:
            profile_key = "corto"
            future_days = TREND_FUTURE_DAYS
            up_threshold = TREND_UP_THRESHOLD
            down_threshold = TREND_DOWN_THRESHOLD

        df_target = self._create_target(
            df_ind,
            future_days=future_days,
            up_threshold=up_threshold,
            down_threshold=down_threshold,
        )
        if df_target.empty:
            raise TrendDetectionServiceException(
                "No fue posible construir la serie de tendencia para el símbolo"
            )

        train_result = self._train_model(df_target, model_type=model_type or "xgboost")
        model = train_result["model"]
        label_encoder = train_result.get("label_encoder")

        last_row = df_ind.tail(1)
        last_features = last_row[FEATURE_COLUMNS]

        # Predicción
        pred_encoded = int(model.predict(last_features)[0])
        
        # Revertir encoding si se usó LabelEncoder (XGBoost)
        if label_encoder is not None:
            pred_mapped = int(label_encoder.inverse_transform([pred_encoded])[0])
            pred = pred_mapped - 1
        else:
            # Random Forest: mapeo directo (0,1,2 -> -1,0,1)
            pred = pred_encoded - 1

        proba_map: Optional[Dict[str, float]] = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(last_features)[0]
            proba_map = {}
            
            if label_encoder is not None:
                # XGBoost con LabelEncoder: mapear probabilidades a clases originales
                classes_encoded = label_encoder.classes_  # Clases originales (ej: [1, 2] o [0, 1, 2])
                for i, cls in enumerate(classes_encoded):
                    original_class = int(cls) - 1  # Revertir +1 del mapeo inicial
                    proba_map[str(original_class)] = float(proba[i])
                # Asegurar que las 3 clases estén presentes (con 0 si no existen)
                for cls_key in ["-1", "0", "1"]:
                    if cls_key not in proba_map:
                        proba_map[cls_key] = 0.0
            else:
                # Random Forest: mapeo directo
                if len(proba) >= 3:
                    proba_map["-1"] = float(proba[0])  # Bajista
                    proba_map["0"] = float(proba[1])   # Lateral
                    proba_map["1"] = float(proba[2])   # Alcista
                elif len(proba) == 2:
                    # Solo 2 clases presentes
                    unique_y = np.sort(df_target["trend"].unique())
                    for i, cls in enumerate(unique_y):
                        proba_map[str(int(cls))] = float(proba[i])
                    for cls_key in ["-1", "0", "1"]:
                        if cls_key not in proba_map:
                            proba_map[cls_key] = 0.0

        trend_map = {
            1: "Tendencia Alcista",
            -1: "Tendencia Bajista",
            0: "Tendencia Lateral",
        }

        trend_label = trend_map.get(pred, "Desconocido")

        # Calcular Fair Value usando el DataFrame con indicadores
        fair_value_data = None
        try:
            fair_value_data = fair_value_service.calculate_fair_value(df_raw)
        except FairValueServiceException:
            # Si falla el cálculo de fair value, continuamos sin él
            pass

        return {
            "symbol": symbol,
            "trend_code": pred,
            "trend_label": trend_label,
            "probabilities": proba_map,
            "n_samples": train_result["n_samples"],
            "classification_report": train_result["report"],
            "model_type": train_result.get("model_type"),
            "profile": profile_key,
            "future_days": future_days,
            "up_threshold": up_threshold,
            "down_threshold": down_threshold,
            "fair_value": fair_value_data,
        }


trend_detection_service = TrendDetectionService()
