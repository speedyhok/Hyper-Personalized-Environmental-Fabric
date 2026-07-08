# h_sef/actuators/home_assistant.py
"""
Home Assistant REST API Actuator Client.
Interfaces with local Home Assistant instances to adjust smart thermostats,
outlets, and multi-sensor systems.
Uses a long-lived access token for REST bearer authorization.
"""

import urllib.request
import json
from typing import Dict, Any

class HomeAssistantActuator:
    def __init__(self, base_url: str = None, access_token: str = None, climate_entity: str = "climate.hsef_thermostat"):
        self.base_url = base_url
        self.token = access_token
        self.climate_entity = climate_entity
        self.enabled = bool(base_url and access_token)

    def is_configured(self) -> bool:
        return self.enabled

    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers Home Assistant REST services using Authorization tokens."""
        temp = payload.get("temp", 22.0)
        
        if not self.enabled:
            return {
                "protocol": "Home Assistant",
                "log": f"[HA Simulation] Climate entity command state updated -> Target: {temp}°C"
            }
            
        url = f"{self.base_url}/api/services/climate/set_temperature"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        ha_payload = {
            "entity_id": self.climate_entity,
            "temperature": temp
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(ha_payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            # Timeout set to 1.5 seconds to avoid blocking the main orchestrator loop
            with urllib.request.urlopen(req, timeout=1.5) as response:
                res_data = json.loads(response.read().decode())
                
            return {
                "protocol": "Home Assistant API",
                "log": f"[Home Assistant] POST success set_temperature -> {self.climate_entity} target: {temp}°C"
            }
        except Exception as e:
            return {
                "protocol": "Home Assistant (Error)",
                "log": f"[HA Connect Fail] REST call to {self.base_url} failed. Reason: {str(e)[:60]}... Falling back to simulated climate."
            }
            
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "Home Assistant Client",
            "active": self.enabled,
            "base_url": self.base_url,
            "entity": self.climate_entity
        }
