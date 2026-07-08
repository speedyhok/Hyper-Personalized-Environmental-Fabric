# tests/test_pipeline.py
"""
Unit tests for the H-SEF multi-modal sensor fusion pipeline and mapping library.
Uses python's built-in unittest library.
"""

import unittest
import numpy as np

from h_sef.pipeline.sync import DataSynchronizer
from h_sef.pipeline.preprocess import SignalPreprocessor
from h_sef.mappings.affect import AffectMapper
from h_sef.context.engine import ContextEngine

class TestHSEFPipeline(unittest.TestCase):
    def test_synchronization(self):
        # Generate mock queues with slightly offset timestamps and varying lengths
        now = 1700000000.0
        eeg_raw = [{"t": now - (10 - i) * 0.01, "v": np.sin(i)} for i in range(1000)]
        ppg_raw = [{"t": now - (10 - i) * 0.02, "v": np.cos(i)} for i in range(500)]
        gsr_raw = [{"t": now - (10 - i) * 0.1, "v": 5.0 + i * 0.01} for i in range(100)]
        env_raw = [{"t": now - (10 - i) * 0.5, "temp": 22.0, "light": 300.0, "noise": 40.0} for i in range(50)]

        timestamps, aligned = DataSynchronizer.synchronize(
            eeg_raw, ppg_raw, gsr_raw, env_raw, target_hz=50.0, window_seconds=2.0
        )

        self.assertEqual(len(timestamps), 100)  # 2.0s * 50Hz = 100 samples
        self.assertIn("eeg", aligned)
        self.assertIn("ppg", aligned)
        self.assertIn("gsr", aligned)
        self.assertIn("room_temp", aligned)
        self.assertEqual(len(aligned["eeg"]), 100)
        self.assertEqual(len(aligned["room_temp"]), 100)

    def test_eeg_preprocessing(self):
        preprocessor = SignalPreprocessor(target_hz=50.0)
        
        # Generate a pure 10.5Hz sine wave (Alpha frequency band)
        t = np.linspace(0, 2.0, 100)
        alpha_wave = np.sin(2 * np.pi * 10.5 * t)
        
        powers = preprocessor.process_eeg(alpha_wave)
        
        # Total relative powers should sum to 1.0
        total_rel = sum(powers.values())
        self.assertAlmostEqual(total_rel, 1.0, places=3)
        
        # Alpha power should be relatively high
        self.assertGreater(powers["alpha"], powers["delta"])
        self.assertGreater(powers["alpha"], powers["gamma"])

    def test_ppg_preprocessing(self):
        preprocessor = SignalPreprocessor(target_hz=50.0)
        
        # Generate simulated clean pulses repeating at 1Hz (60 BPM)
        # Peak index every 50 samples
        ppg = np.zeros(300)
        for i in range(5):
            peak_idx = 50 + i * 50
            # Create Gaussian peak
            for offset in range(-5, 6):
                ppg[peak_idx + offset] = np.exp(-(offset / 2.0) ** 2)
                
        features = preprocessor.process_ppg(ppg)
        
        # Instantaneous Heart Rate should be around 60 BPM
        self.assertTrue(55.0 <= features["hr"] <= 65.0)
        self.assertIn("rmssd", features)

    def test_gsr_preprocessing(self):
        preprocessor = SignalPreprocessor(target_hz=50.0)
        
        # Constant baseline + a single phasic surge
        t = np.linspace(0, 4.0, 200)
        gsr = 5.0 + 3.0 * np.exp(-((t - 2.0) / 0.5) ** 2)
        
        features = preprocessor.process_gsr(gsr)
        
        # Tonic level should be close to baseline
        self.assertTrue(4.5 <= features["tonic"] <= 5.5)
        # Phasic strength should capture the surge peak amplitude
        self.assertGreater(features["phasic"], 1.0)

    def test_affect_mapping(self):
        mapper = AffectMapper()
        
        # Case 1: High stress inputs (High beta/gamma, high HR, high GSR phasic, low HRV)
        eeg_stressed = {"delta": 0.05, "theta": 0.05, "alpha": 0.05, "beta": 0.5, "gamma": 0.35}
        ppg_stressed = {"hr": 110.0, "rmssd": 15.0}
        gsr_stressed = {"gsr_clean": 10.0, "tonic": 8.0, "phasic": 1.5}
        
        res_stressed = mapper.compute_cognitive_state(eeg_stressed, ppg_stressed, gsr_stressed)
        
        # Case 2: Deep relaxed inputs (High alpha, low HR, low GSR, high HRV)
        eeg_relaxed = {"delta": 0.1, "theta": 0.1, "alpha": 0.7, "beta": 0.05, "gamma": 0.05}
        ppg_relaxed = {"hr": 58.0, "rmssd": 85.0}
        gsr_relaxed = {"gsr_clean": 4.5, "tonic": 4.5, "phasic": 0.0}
        
        res_relaxed = mapper.compute_cognitive_state(eeg_relaxed, ppg_relaxed, gsr_relaxed)
        
        # Stressed arousal should be higher than relaxed arousal
        self.assertGreater(res_stressed["arousal"], res_relaxed["arousal"])
        # Stressed valence should be lower than relaxed valence
        self.assertLess(res_stressed["valence"], res_relaxed["valence"])
        # Stressed state index should be high, relaxed should be low
        self.assertGreater(res_stressed["stress_index"], res_relaxed["stress_index"])
        self.assertIn("Relaxed", res_relaxed["state_label"])

    def test_context_engine(self):
        engine = ContextEngine()
        vector = engine.get_context_vector()
        
        self.assertIn("circadian_phase", vector)
        self.assertIn("calendar_stress", vector)
        self.assertIn("next_event", vector)
        self.assertIn("outdoor_weather", vector)

if __name__ == "__main__":
    unittest.main()
