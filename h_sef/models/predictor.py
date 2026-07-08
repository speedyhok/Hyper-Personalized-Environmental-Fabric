# h_sef/models/predictor.py
"""
Predictive Intervention Modeler.
Trains a Scikit-Learn regression model on synthetic historical data to predict
how proposed sensory adjustments (Phase 3 outputs: temperature shifts, lighting, decibels)
will affect the user's future physiological state (Valence, Arousal, Cognitive Load).
"""

from typing import Dict, Any, List
import numpy as np
from sklearn.linear_model import Ridge

class InterventionPredictor:
    def __init__(self):
        # We use a Ridge Regression model to predict state shifts:
        # Inputs (6 dimensions):
        # - 0: Current Valence, 1: Current Arousal, 2: Current Cognitive Load
        # - 3: Proposed Δ Temp, 4: Proposed Δ Light, 5: Proposed Δ Noise
        # Outputs (3 dimensions):
        # - 0: Expected Valence, 1: Expected Arousal, 2: Expected Cognitive Load
        self.model = Ridge(alpha=1.0)
        
        # Fit model on a synthetic baseline to represent historical training
        self._fit_on_synthetic_data()

    def _fit_on_synthetic_data(self):
        """Generates a synthetic history and trains the model on physiological response curves."""
        np.random.seed(42)
        n_samples = 500
        
        # Inputs: starting states + sensory changes
        start_valence = np.random.uniform(-0.8, 0.8, n_samples)
        start_arousal = np.random.uniform(-0.8, 0.8, n_samples)
        start_load = np.random.uniform(0.1, 0.9, n_samples)
        
        delta_temp = np.random.uniform(-3.0, 3.0, n_samples)   # Δ Celsius
        delta_light = np.random.uniform(-200.0, 200.0, n_samples) # Δ Lux
        delta_noise = np.random.uniform(-15.0, 15.0, n_samples)  # Δ Decibels
        
        X = np.stack([
            start_valence, start_arousal, start_load,
            delta_temp, delta_light, delta_noise
        ], axis=1)
        
        # Outputs: predicted final states modulated by physical principles
        # 1. Warm temperatures (>21C) increase arousal, cooling reduces stress/arousal
        # 2. Dimming lights reduces arousal and increases valence if stressed
        # 3. Decreasing noise increases valence and reduces cognitive load/arousal
        
        # Valence shifts
        new_valence = start_valence - (0.05 * delta_temp) - (0.02 * delta_noise)
        # Surcharge valence if noise is reduced
        new_valence += np.where(delta_noise < 0, 0.1, 0.0)
        
        # Arousal shifts
        new_arousal = start_arousal + (0.08 * delta_temp) + (0.001 * delta_light) + (0.04 * delta_noise)
        
        # Cognitive Load shifts
        new_load = start_load + (0.01 * delta_noise) + (0.0005 * delta_light)
        new_load = np.where(delta_light < -100, new_load - 0.05, new_load) # Dimming light aids focus
        
        # Add random biological variance (noise)
        new_valence += np.random.normal(0, 0.05, n_samples)
        new_arousal += np.random.normal(0, 0.05, n_samples)
        new_load += np.random.normal(0, 0.03, n_samples)
        
        # Clip to physiological boundaries
        new_valence = np.clip(new_valence, -1.0, 1.0)
        new_arousal = np.clip(new_arousal, -1.0, 1.0)
        new_load = np.clip(new_load, 0.0, 1.0)
        
        y = np.stack([new_valence, new_arousal, new_load], axis=1)
        
        # Fit Ridge Regression
        self.model.fit(X, y)

    def predict_outcome(
        self,
        current_state: Dict[str, float],
        delta_temp: float,
        delta_light: float,
        delta_noise: float
    ) -> Dict[str, float]:
        """
        Predicts the expected Valence, Arousal, and Cognitive Load
        after applying physical environmental adjustments.
        """
        v = current_state.get("valence", 0.0)
        a = current_state.get("arousal", 0.0)
        cl = current_state.get("cognitive_load", 0.5)
        
        X_test = np.array([[v, a, cl, delta_temp, delta_light, delta_noise]])
        y_pred = self.model.predict(X_test)[0]
        
        # Clip predictions to bounding spaces
        pred_v = max(-1.0, min(1.0, float(y_pred[0])))
        pred_a = max(-1.0, min(1.0, float(y_pred[1])))
        pred_cl = max(0.0, min(1.0, float(y_pred[2])))
        
        return {
            "predicted_valence": round(pred_v, 3),
            "predicted_arousal": round(pred_a, 3),
            "predicted_cognitive_load": round(pred_cl, 3)
        }
