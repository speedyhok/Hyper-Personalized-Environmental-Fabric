# h_sef/orchestrator.py
"""
H-SEF Firmware Orchestrator.
Main loop coordinator that synchronizes inputs, runs CSM models,
invokes the RL control policy, applies safety override blocks,
and dispatches commands to standardized actuators.
"""

from typing import Dict, Any, List
import numpy as np

from h_sef.actuators.standard_actuators import SmartLightingBridge, ClimateController, ScentDiffuser
from h_sef.actuators.safety import PsychologicalSafetyManager

# Physical Hardware bridges
from h_sef.actuators.hue_bridge import PhilipsHueBridgeActuator
from h_sef.actuators.home_assistant import HomeAssistantActuator

class HSEFOrchestrator:
    def __init__(self, csm_predictor, intervention_predictor, rl_policy, context_engine):
        # Actuators
        self.lighting = SmartLightingBridge()
        self.climate = ClimateController()
        self.diffuser = ScentDiffuser()
        
        # Connect to actuators
        self.lighting.connect()
        self.climate.connect()
        self.diffuser.connect()
        
        # Safety Manager
        self.safety = PsychologicalSafetyManager(lockout_seconds=15.0)
        
        # Models & Policies
        self.csm_predictor = csm_predictor
        self.intervention_predictor = intervention_predictor
        self.rl_policy = rl_policy
        self.context_engine = context_engine
        
        # Physical bridges (start unconfigured)
        self.hue = PhilipsHueBridgeActuator()
        self.ha = HomeAssistantActuator()
        
        # Command logs history
        self.command_logs: List[str] = []

    def configure_hardware(self, hue_ip: str = None, hue_key: str = None, ha_url: str = None, ha_token: str = None):
        """Updates connection credentials for physical actuators in real-time."""
        self.hue = PhilipsHueBridgeActuator(hue_ip, hue_key)
        self.ha = HomeAssistantActuator(ha_url, ha_token)

    def execute_control_cycle(
        self,
        csm_state: Dict[str, Any],
        predicted_outcome: Dict[str, Any],
        rl_action_idx: int,
        synthesis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Coordinates the actuator updates. Checks for active lockouts,
        dispatches Matter/MQTT/WebSocket commands, and records the logs.
        """
        dispatched_logs = []
        
        # 1. Coordinate Lighting
        if self.safety.is_automation_allowed("lighting"):
            light_payload = {
                "cct": synthesis["light"]["cct"],
                "lux": synthesis["light"]["lux"],
                "rgb": synthesis["light"]["rgb"]
            }
            if self.hue.is_configured():
                light_cmd = self.hue.send_command(light_payload)
            else:
                light_cmd = self.lighting.send_command(light_payload)
            dispatched_logs.append(light_cmd)
        else:
            dispatched_logs.append({
                "protocol": "Blocked",
                "log": "[SAFETY LOCK] Matter Light adjustment blocked. Manual override active."
            })
            
        # 2. Coordinate Climate
        if self.safety.is_automation_allowed("climate"):
            target_temp = 21.0 if rl_action_idx == 0 else (23.0 if rl_action_idx == 1 else 22.0)
            
            if self.ha.is_configured():
                climate_cmd = self.ha.send_command({"temp": target_temp})
            else:
                climate_cmd = self.climate.send_command({"temp": target_temp})
            dispatched_logs.append(climate_cmd)
        else:
            dispatched_logs.append({
                "protocol": "Blocked",
                "log": "[SAFETY LOCK] HVAC adjustment blocked. Manual override active."
            })
            
        # 3. Coordinate Scent Diffuser
        diffuser_cmd = self.diffuser.send_command({"scent": synthesis["olfactory"]["scent"]})
        dispatched_logs.append(diffuser_cmd)
        
        # Store logs history
        for item in dispatched_logs:
            self.command_logs.append(item["log"])
            if len(self.command_logs) > 50:
                self.command_logs.pop(0)
                
        return dispatched_logs

    def get_logs(self) -> List[str]:
        return list(self.command_logs)
