# h_sef/actuators/hue_bridge.py
"""
Philips Hue Bridge Actuator Client.
Sends HTTP PUT requests to a local Philips Hue Bridge to control color temperature,
brightness (0-254), and color settings. Handles connection drops gracefully.
"""

import urllib.request
import json
from typing import Dict, Any

class PhilipsHueBridgeActuator:
    def __init__(self, ip: str = None, app_key: str = None, light_id: str = "1"):
        self.ip = ip
        self.app_key = app_key
        self.light_id = light_id
        self.enabled = bool(ip and app_key)

    def is_configured(self) -> bool:
        return self.enabled

    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Converts lighting targets (CCT/Lux) and sends PUT request to Hue light API."""
        cct = payload.get("cct", 4000)
        lux = payload.get("lux", 250.0)
        rgb = payload.get("rgb", (255, 255, 255))
        
        # Scale Lux (0-500) to Hue brightness value (0-254)
        bri = int(max(1, min(254, (lux / 500.0) * 254.0)))
        # Convert CCT to Hue Mireds (153-500): Mireds = 1e6 / CCT
        mireds = int(max(153, min(500, 1000000.0 / cct)))
        
        hue_body = {
            "on": True,
            "bri": bri,
            "ct": mireds
        }
        
        if not self.enabled:
            return {
                "protocol": "Philips Hue",
                "log": f"[Hue Simulation] Command state updated -> Mireds: {mireds}, Brightness: {bri}"
            }
            
        url = f"http://{self.ip}/api/{self.app_key}/lights/{self.light_id}/state"
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(hue_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            # Timeout set to 1.5 seconds to avoid blocking the main orchestrator loop
            with urllib.request.urlopen(req, timeout=1.5) as response:
                res_data = json.loads(response.read().decode())
                
            return {
                "protocol": "Philips Hue Bridge API",
                "log": f"[Hue Bridge] PUT success to Bridge http://{self.ip} -> Light {self.light_id} updated. CT: {cct}K, Bri: {bri}"
            }
        except Exception as e:
            return {
                "protocol": "Philips Hue Bridge (Error)",
                "log": f"[Hue Connect Fail] Failed to connect to bridge at {self.ip}. Reason: {str(e)[:60]}... Falling back to simulated lighting."
            }
            
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "Philips Hue Bridge Client",
            "active": self.enabled,
            "ip": self.ip,
            "light_id": self.light_id
        }
