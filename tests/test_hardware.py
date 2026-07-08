# tests/test_hardware.py
"""
Unit tests for Phase 5 Physical Hardware integrations.
Verifies smartwatch webhook ingress buffers and smart home REST bridges.
"""

import unittest
import time
from unittest.mock import MagicMock

from h_sef.pipeline.wearable_ingest import WearableIngestHub
from h_sef.actuators.hue_bridge import PhilipsHueBridgeActuator
from h_sef.actuators.home_assistant import HomeAssistantActuator
from h_sef.orchestrator import HSEFOrchestrator

class TestPhysicalHardware(unittest.TestCase):
    def test_wearable_ingest_hub(self):
        hub = WearableIngestHub()
        
        # Initially inactive
        self.assertFalse(hub.is_active())
        self.assertEqual(hub.device_name, "None")
        
        # Register metrics
        hub.register_metrics(heart_rate=78.0, hrv_rmssd=45.0, gsr=1.5, source="Garmin Watch")
        
        self.assertTrue(hub.is_active())
        metrics = hub.get_override_metrics()
        self.assertEqual(metrics["heart_rate"], 78.0)
        self.assertEqual(metrics["hrv_rmssd"], 45.0)
        self.assertEqual(metrics["gsr"], 1.5)
        self.assertEqual(metrics["source"], "Garmin Watch")
        
        # Test timeout (we can mock last_received back in time)
        hub.last_received = time.time() - 50.0
        self.assertFalse(hub.is_active())

    def test_hue_bridge_actuator_simulation(self):
        # Unconfigured should return simulation log
        actuator = PhilipsHueBridgeActuator()
        self.assertFalse(actuator.is_configured())
        
        res = actuator.send_command({"cct": 3000, "lux": 200})
        self.assertIn("[Hue Simulation]", res["log"])
        self.assertIn("Mireds: 333", res["log"])

    def test_home_assistant_actuator_simulation(self):
        actuator = HomeAssistantActuator()
        self.assertFalse(actuator.is_configured())
        
        res = actuator.send_command({"temp": 20.5})
        self.assertIn("[HA Simulation]", res["log"])
        self.assertIn("Target: 20.5°C", res["log"])

    def test_orchestrator_hardware_configuration(self):
        csm_predictor = MagicMock()
        intervention_predictor = MagicMock()
        rl_policy = MagicMock()
        context_engine = MagicMock()
        
        orchestrator = HSEFOrchestrator(csm_predictor, intervention_predictor, rl_policy, context_engine)
        
        # Configure hardware
        orchestrator.configure_hardware(
            hue_ip="192.168.1.50",
            hue_key="my_secret_hue_key",
            ha_url="http://192.168.1.100:8123",
            ha_token="my_secret_ha_token"
        )
        
        self.assertTrue(orchestrator.hue.is_configured())
        self.assertTrue(orchestrator.ha.is_configured())
        
        self.assertEqual(orchestrator.hue.ip, "192.168.1.50")
        self.assertEqual(orchestrator.ha.base_url, "http://192.168.1.100:8123")

if __name__ == "__main__":
    unittest.main()
