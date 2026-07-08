# tests/test_integration.py
"""
Integration tests for Phase 4 System Integration.
Verifies standardized actuators, safety override lockout mechanisms, and orchestrator loops.
"""

import unittest
import time
from unittest.mock import MagicMock

from h_sef.actuators.standard_actuators import SmartLightingBridge, ClimateController, ScentDiffuser
from h_sef.actuators.safety import PsychologicalSafetyManager
from h_sef.orchestrator import HSEFOrchestrator

class TestSystemIntegration(unittest.TestCase):
    def test_standard_actuators(self):
        light = SmartLightingBridge()
        climate = ClimateController()
        diffuser = ScentDiffuser()
        
        self.assertTrue(light.connect())
        self.assertTrue(climate.connect())
        self.assertTrue(diffuser.connect())
        
        # Test command outputs
        l_res = light.send_command({"cct": 4000, "lux": 250, "rgb": (255, 255, 255)})
        self.assertEqual(l_res["protocol"], "Matter/CoAP")
        self.assertIn("CCT: 4000K", l_res["log"])
        
        c_res = climate.send_command({"temp": 21.5})
        self.assertEqual(c_res["protocol"], "MQTT")
        self.assertIn("Target: 21.5°C", c_res["log"])
        
        d_res = diffuser.send_command({"scent": "Peppermint"})
        self.assertEqual(d_res["protocol"], "WebSocket")
        self.assertIn("Scent: Peppermint", d_res["log"])

    def test_safety_override_manager(self):
        # Create safety manager with small lockout for quick test
        safety = PsychologicalSafetyManager(lockout_seconds=0.2)
        
        # Initially automation is allowed
        self.assertTrue(safety.is_automation_allowed("lighting"))
        self.assertTrue(safety.is_automation_allowed("climate"))
        
        # Register manual override on lighting
        safety.register_manual_override("lighting")
        
        # Lighting should be locked, climate still open
        self.assertFalse(safety.is_automation_allowed("lighting"))
        self.assertTrue(safety.is_automation_allowed("climate"))
        
        # Wait for lockout to expire
        time.sleep(0.25)
        self.assertTrue(safety.is_automation_allowed("lighting"))

    def test_orchestrator_control_cycle(self):
        # Mock models
        csm_predictor = MagicMock()
        intervention_predictor = MagicMock()
        rl_policy = MagicMock()
        context_engine = MagicMock()
        
        orchestrator = HSEFOrchestrator(csm_predictor, intervention_predictor, rl_policy, context_engine)
        
        csm_state = {"valence": 0.5, "arousal": 0.2, "cognitive_load": 0.3}
        predicted_outcome = {}
        rl_action_idx = 2
        synthesis = {
            "light": {"cct": 4000, "lux": 250, "rgb": (255, 255, 255), "lighting_label": "Test"},
            "sound": {},
            "olfactory": {"scent": "Lavender"}
        }
        
        # Run loop
        logs = orchestrator.execute_control_cycle(csm_state, predicted_outcome, rl_action_idx, synthesis)
        self.assertEqual(len(logs), 3) # Lighting, Climate, Diffuser
        self.assertIn("Matter Light", logs[0]["log"])
        self.assertIn("MQTT HVAC", logs[1]["log"])
        self.assertIn("ESP32 Diffuser", logs[2]["log"])
        
        # Apply manual lockout and verify blocked logs
        orchestrator.safety.register_manual_override("lighting")
        logs2 = orchestrator.execute_control_cycle(csm_state, predicted_outcome, rl_action_idx, synthesis)
        self.assertIn("[SAFETY LOCK]", logs2[0]["log"])

if __name__ == "__main__":
    unittest.main()
