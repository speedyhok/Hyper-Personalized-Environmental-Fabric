# h_sef/actuators/safety.py
"""
Psychological Safety Manager.
Enforces that user manual overrides (e.g., manually adjusting room temperature or lights)
temporarily block (lockout) automated RL agent adjustments to avoid control conflicts.
"""

import time
from typing import Dict, Any

class PsychologicalSafetyManager:
    def __init__(self, lockout_seconds: float = 15.0):
        # Maps actuator name -> timestamp of last manual override
        self.lockout_seconds = lockout_seconds
        self.overrides: Dict[str, float] = {}

    def register_manual_override(self, actuator_name: str):
        """Saves current timestamp to lock out automation for this actuator."""
        self.overrides[actuator_name] = time.time()

    def is_automation_allowed(self, actuator_name: str) -> bool:
        """Returns True if automation is allowed; False if a manual lockout is active."""
        last_override = self.overrides.get(actuator_name, 0.0)
        elapsed = time.time() - last_override
        return elapsed > self.lockout_seconds

    def get_lockout_status(self) -> Dict[str, Any]:
        """Compiles active lockout details and seconds remaining."""
        now = time.time()
        status = {}
        overall_paused = False
        
        for act in ["lighting", "climate"]:
            last = self.overrides.get(act, 0.0)
            elapsed = now - last
            remaining = max(0.0, self.lockout_seconds - elapsed)
            
            is_locked = remaining > 0.0
            if is_locked:
                overall_paused = True
                
            status[act] = {
                "manual_active": is_locked,
                "seconds_remaining": round(remaining, 1)
            }
            
        status["overall_automation_paused"] = overall_paused
        return status
