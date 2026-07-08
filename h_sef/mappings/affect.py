# h_sef/mappings/affect.py
"""
Library of psycho-physical mappings.
Correlates computed biometric features (EEG spectral power, HRV, GSR tonic/phasic)
with internal affective states (Valence & Arousal) and Cognitive Load.
"""

from typing import Dict, Any

class AffectMapper:
    def __init__(self):
        # Rolling baselines to adapt to user differences (simplifies calibration)
        self.hr_baseline = 72.0
        self.rmssd_baseline = 45.0
        self.gsr_baseline = 6.0
        
        # Adaptation coefficient (slow moving average updates)
        self.alpha_adapt = 0.005

    def update_baselines(self, hr: float, rmssd: float, gsr: float):
        """Gradually updates physiological baselines for personalized mapping."""
        # Simple exponential moving average calibration
        self.hr_baseline += (hr - self.hr_baseline) * self.alpha_adapt
        self.rmssd_baseline += (rmssd - self.rmssd_baseline) * self.alpha_adapt
        self.gsr_baseline += (gsr - self.gsr_baseline) * self.alpha_adapt

    def compute_cognitive_state(
        self,
        eeg_features: Dict[str, float],
        ppg_features: Dict[str, float],
        gsr_features: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Maps processed features to Cognitive Load and Affective State (Valence/Arousal).
        
        Mathematical Formulations:
        - Cognitive Load: Derived from theta/alpha or (theta + beta)/alpha power ratios.
        - Arousal: Correlates positively with HR and Phasic GSR amplitude.
        - Valence: Positive correlation with HRV (RMSSD) and Alpha power.
        """
        hr = ppg_features.get("hr", 70.0)
        rmssd = ppg_features.get("rmssd", 40.0)
        gsr_val = gsr_features.get("gsr_clean", 5.0)
        phasic_gsr = gsr_features.get("phasic", 0.0)
        
        # Update rolling averages to calibrate on the fly
        self.update_baselines(hr, rmssd, gsr_val)

        # 1. Cognitive Load Score (0.0 to 1.0)
        # Ratio of Theta (focus/processing) and Beta (arousal) to Alpha (relaxation)
        t_pow = eeg_features.get("theta", 0.2)
        b_pow = eeg_features.get("beta", 0.2)
        a_pow = eeg_features.get("alpha", 0.2)
        
        # Standard EEG cognitive workload metric
        workload_ratio = (t_pow + b_pow) / max(0.01, a_pow)
        # Normalize workload ratio to a 0.0 - 1.0 score using a sigmoid function
        # A ratio of ~1.0 maps to 0.4, ratio of ~3.0 maps to 0.8
        cognitive_load = 1.0 / (1.0 + float(complex(2.71828 ** (-0.8 * (workload_ratio - 1.5))).real))
        cognitive_load = max(0.0, min(1.0, cognitive_load))

        # 2. Arousal (-1.0 to 1.0)
        # Arousal increases when HR exceeds baseline, and when phasic GSR spikes
        hr_dev = (hr - self.hr_baseline) / max(5.0, self.hr_baseline * 0.1)
        gsr_dev = phasic_gsr * 2.0  # Phasic spikes indicate sympathetic activation
        
        arousal = (0.4 * hr_dev) + (0.6 * gsr_dev)
        arousal = max(-1.0, min(1.0, arousal))

        # 3. Valence (-1.0 to 1.0)
        # High HRV (RMSSD) and Alpha activity correlate with positive valence (relaxation/comfort).
        # Low HRV + high arousal correlates with stress/panic/negative valence.
        hrv_dev = (rmssd - self.rmssd_baseline) / max(5.0, self.rmssd_baseline * 0.2)
        
        # High alpha relative power means relaxation; low alpha with high beta/gamma means anxiety/stress
        alpha_factor = (a_pow - 0.2) * 2.0
        
        # Valence penalty for high stress (low hrv + high arousal)
        stress_penalty = -0.5 * max(0.0, arousal) if hrv_dev < 0 else 0.0
        
        valence = (0.5 * hrv_dev) + (0.3 * alpha_factor) + stress_penalty
        valence = max(-1.0, min(1.0, valence))

        # 4. Stress and Focus Indices (0.0 to 1.0)
        # Stress: high arousal, negative valence
        stress_index = max(0.0, min(1.0, (arousal - valence) / 2.0))
        # Focus: high cognitive load, positive/neutral valence, moderate-high arousal
        focus_index = max(0.0, min(1.0, cognitive_load * (1.0 + valence) / 2.0))

        # 5. Discrete Affective Label
        # Divide circumplex into 4 quadrants
        if arousal >= 0.1:
            if valence >= 0.1:
                label = "Flow / Focused Excitement"
            elif valence <= -0.1:
                label = "Anxious / Stressed"
            else:
                label = "High Alert / Active Work"
        elif arousal <= -0.1:
            if valence >= 0.1:
                label = "Calm / Deeply Relaxed"
            elif valence <= -0.1:
                label = "Fatigued / Bored"
            else:
                label = "Drowsy / Quiet State"
        else:
            label = "Neutral State"

        return {
            "cognitive_load": round(cognitive_load, 3),
            "valence": round(valence, 3),
            "arousal": round(arousal, 3),
            "stress_index": round(stress_index, 3),
            "focus_index": round(focus_index, 3),
            "state_label": label
        }
