# h_sef/actuators/standard_actuators.py
"""
Standard actuator implementations.
Simulates sending JSON commands via Matter, MQTT, and WebSocket protocols to:
- Smart lighting bridges (Philips Hue / Matter)
- Climate controls (Modbus/MQTT Thermostats)
- Scent atomizers (ESP32 WebSockets)
"""

from typing import Dict, Any
from h_sef.actuators.base import BaseActuator

class SmartLightingBridge(BaseActuator):
    def __init__(self):
        super().__init__("Matter Lighting Bridge")

    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        cct = payload.get("cct", 4000)
        lux = payload.get("lux", 250.0)
        rgb = payload.get("rgb", (255, 255, 255))
        
        cmd_str = f"[Matter Light] POST http://192.168.1.50/api/lights/state -> CCT: {cct}K, Lux: {int(lux)}, RGB: {rgb}"
        self.last_command = {
            "protocol": "Matter/CoAP",
            "endpoint": "http://192.168.1.50/api/lights/state",
            "payload": {"on": True, "bri": int(lux), "ct": cct, "rgb": rgb},
            "log": cmd_str
        }
        return self.last_command

class ClimateController(BaseActuator):
    def __init__(self):
        super().__init__("HVAC Smart Thermostat")

    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        temp = payload.get("temp", 22.0)
        
        cmd_str = f"[MQTT HVAC] PUBLISH hvac/set/temperature -> Target: {temp}°C"
        self.last_command = {
            "protocol": "MQTT",
            "topic": "hvac/set/temperature",
            "payload": {"target_temp": temp, "fan_mode": "Auto"},
            "log": cmd_str
        }
        return self.last_command

class ScentDiffuser(BaseActuator):
    def __init__(self):
        super().__init__("ESP32 Olfactory Diffuser")

    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        scent = payload.get("scent", "Neutral")
        
        cmd_str = f"[ESP32 Diffuser] WS send ws://192.168.1.80/control -> Scent: {scent}, Misting: 3000ms"
        self.last_command = {
            "protocol": "WebSocket",
            "url": "ws://192.168.1.80/control",
            "payload": {"action": "mist", "cartridge": scent, "duration_ms": 3000},
            "log": cmd_str
        }
        return self.last_command
