# h_sef/actuators/base.py
"""
Base classes for standardized actuators.
Defines interface contracts for physical IoT integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseActuator(ABC):
    def __init__(self, name: str):
        self.name = name
        self.connected = False
        self.last_command = {}

    def connect(self) -> bool:
        """Simulates connecting to local network bridges (Matter, MQTT, HTTP)."""
        self.connected = True
        return True

    @abstractmethod
    def send_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches commands to hardware."""
        pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self.connected,
            "last_command": self.last_command
        }
