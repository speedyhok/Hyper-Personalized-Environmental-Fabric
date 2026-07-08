# tests/test_csm.py
"""
Unit tests for Phase 2 Cognitive State Modeling (CSM) Core.
Verifies sequence predictions, causal attributions, state space paths, and intervention prognosis.
"""

import unittest
import numpy as np
import torch

from h_sef.models.csm_core import CognitiveStateSequencePredictor, CognitiveStateSpace
from h_sef.models.predictor import InterventionPredictor

class TestCSMCore(unittest.TestCase):
    def test_sequence_predictor_forward(self):
        predictor = CognitiveStateSequencePredictor()
        
        # Batch size = 1, sequence length = 50, features = 11
        seq_tensor = torch.randn(1, 50, 11)
        
        out = predictor(seq_tensor)
        self.assertEqual(out.shape, (1, 3)) # (Valence, Arousal, Load)
        
        # Outputs must be floating values
        self.assertTrue(isinstance(out[0, 0].item(), float))

    def test_causal_attribution(self):
        predictor = CognitiveStateSequencePredictor()
        
        # Sequence of shape [100, 11]
        seq_np = np.random.randn(100, 11)
        
        attr = predictor.calculate_causal_attribution(seq_np)
        
        self.assertIn("workload", attr)
        self.assertIn("environment", attr)
        self.assertIn("physiology", attr)
        
        # Sum of percentages should be close to 100%
        total = attr["workload"] + attr["environment"] + attr["physiology"]
        self.assertAlmostEqual(total, 100.0, delta=1.0)

    def test_state_space_interpolation(self):
        start = (-0.5, 0.5)  # Anxious Focus
        end = (0.6, -0.2)    # Calm concentration
        
        path = CognitiveStateSpace.interpolate_path(start, end, steps=10)
        
        self.assertEqual(len(path), 10)
        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], end)
        
        # Midpoint valence should be between start and end
        self.assertTrue(start[0] < path[5][0] < end[0])

    def test_intervention_predictor(self):
        predictor = InterventionPredictor()
        
        current_state = {
            "valence": -0.4,
            "arousal": 0.6,
            "cognitive_load": 0.8
        }
        
        # Simulate cooling down the room and dimming light
        prognosis = predictor.predict_outcome(
            current_state,
            delta_temp=-2.0,
            delta_light=-100.0,
            delta_noise=-5.0
        )
        
        self.assertIn("predicted_valence", prognosis)
        self.assertIn("predicted_arousal", prognosis)
        self.assertIn("predicted_cognitive_load", prognosis)
        
        # Out should be within physical limits
        self.assertTrue(-1.0 <= prognosis["predicted_valence"] <= 1.0)
        self.assertTrue(-1.0 <= prognosis["predicted_arousal"] <= 1.0)
        self.assertTrue(0.0 <= prognosis["predicted_cognitive_load"] <= 1.0)

if __name__ == "__main__":
    unittest.main()
