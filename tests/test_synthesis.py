# tests/test_synthesis.py
"""
Unit tests for Phase 3 Generative Sensory Synthesis.
Verifies sound/light synthesis, scent dispersion models, and Q-learning policy updates.
Grounded in biophysical and fluid transport models.
"""

import unittest
import numpy as np

from h_sef.synthesis.generators import AcousticSynthesizer, VisualSynthesizer
from h_sef.synthesis.olfactory import OlfactoryDispersionEngine
from h_sef.synthesis.policy import ClosedLoopRLPolicy

class TestSensorySynthesis(unittest.TestCase):
    def test_acoustic_synthesis(self):
        # High stress state should generate Alpha/Theta entrainment (approx 7.3Hz offset)
        stressed_beats = AcousticSynthesizer.synthesize_binaural_parameters(focus_index=0.1, stress_index=0.8)
        self.assertEqual(stressed_beats["binaural_offset"], 7.3)
        self.assertEqual(stressed_beats["carrier_frequency"], 120.0)
        
        # High focus state should generate Gamma entrainment (approx 31.7Hz offset)
        focused_beats = AcousticSynthesizer.synthesize_binaural_parameters(focus_index=0.8, stress_index=0.1)
        self.assertEqual(focused_beats["binaural_offset"], 31.7)
        self.assertEqual(focused_beats["carrier_frequency"], 225.0)

    def test_visual_synthesis(self):
        # Stressed state -> Warm dim lights (CCT = 2230K, Lux = 66.0)
        stressed_light = VisualSynthesizer.synthesize_lighting(focus_index=0.1, stress_index=0.8)
        self.assertEqual(stressed_light["cct"], 2230)
        self.assertEqual(stressed_light["lux"], 66.0)
        
        # Focused state -> Cool bright daylight (CCT = 5240K, Lux = 332.0)
        focused_light = VisualSynthesizer.synthesize_lighting(focus_index=0.8, stress_index=0.1)
        self.assertEqual(focused_light["cct"], 5240)
        self.assertEqual(focused_light["lux"], 332.0)

    def test_olfactory_dispersion(self):
        engine = OlfactoryDispersionEngine()
        
        # Distance = 2.0m, Wind = 0.5m/s, Device lag = 1.0s -> expected travel time = 4.0s, total latency = 5.0s
        res = engine.simulate_scent_dispersion(distance_meters=2.0, wind_velocity_mps=0.5, scent_type="Lavender")
        
        self.assertEqual(res["scent"], "Lavender")
        self.assertEqual(res["transport_latency_seconds"], 5.0)
        self.assertIn("estimated_peak_intensity_pct", res)
        self.assertIn("dispersion_status", res)

    def test_rl_policy(self):
        policy = ClosedLoopRLPolicy(target_state="Focus")
        
        # Check action labels and size
        self.assertEqual(policy.n_actions, 6)
        
        # Select action
        action_idx, label = policy.select_action(valence=-0.5, arousal=0.8, cog_load=0.7)
        self.assertTrue(0 <= action_idx < 6)
        self.assertTrue(isinstance(label, str))
        
        # Reward calculation
        # If Valence is negative (-0.5) and arousal is far from target (arousal = 0.8, target = 0.4), reward should be negative
        reward = policy.compute_reward(valence=-0.5, arousal=0.8, action_idx=action_idx)
        self.assertLess(reward, 0.0)
        
        # Q-update
        curr_state = {"valence": -0.5, "arousal": 0.8, "cognitive_load": 0.7}
        next_state = {"valence": -0.2, "arousal": 0.5, "cognitive_load": 0.6}
        
        new_q = policy.update_q_value(curr_state, action_idx, reward, next_state)
        self.assertTrue(isinstance(new_q, float))

if __name__ == "__main__":
    unittest.main()
