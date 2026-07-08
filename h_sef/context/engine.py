# h_sef/context/engine.py
"""
Context Engine for H-SEF.
Ingests time of day (circadian rhythms), local weather patterns, and calendar events
to output a contextual stress factor and circadian classification.
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Tuple

class ContextEngine:
    def __init__(self):
        # Sample simulated calendar events
        self.calendar_events = [
            {"time": "09:00", "title": "Morning Sync", "importance": "low", "type": "meeting"},
            {"time": "11:00", "title": "Project Review Meeting", "importance": "high", "type": "meeting"},
            {"time": "14:00", "title": "Focused Programming Block", "importance": "medium", "type": "work"},
            {"time": "17:00", "title": "Decompress/Yoga Session", "importance": "low", "type": "rest"},
            {"time": "20:00", "title": "Evening Review", "importance": "medium", "type": "work"}
        ]
        self.weather = {"temp": 18.5, "condition": "Overcast", "humidity": 72}

    def get_circadian_phase(self) -> Dict[str, Any]:
        """Classifies the current time into circadian phases."""
        now_dt = datetime.now()
        hour = now_dt.hour
        
        if 6 <= hour < 11:
            phase = "Morning Activation"
            circadian_stress = 0.1 # Normally fresh
        elif 11 <= hour < 15:
            phase = "Midday Focus / High Alert"
            circadian_stress = 0.2
        elif 15 <= hour < 18:
            phase = "Afternoon Dip"
            circadian_stress = 0.3 # Physiological fatigue
        elif 18 <= hour < 22:
            phase = "Evening Wind-Down"
            circadian_stress = 0.1
        else:
            phase = "Night / Sleep Mode"
            circadian_stress = 0.0

        return {"phase": phase, "circadian_stress": circadian_stress}

    def get_calendar_stress(self) -> Tuple[float, str]:
        """
        Calculates upcoming calendar stress based on proximity to meetings.
        Returns a stress factor (0.0 to 1.0) and the name of the next event.
        """
        now_dt = datetime.now()
        now_minutes = now_dt.hour * 60 + now_dt.minute
        
        next_event = None
        min_diff = 99999
        
        for event in self.calendar_events:
            ev_hour, ev_min = map(int, event["time"].split(":"))
            ev_minutes = ev_hour * 60 + ev_min
            
            diff = ev_minutes - now_minutes
            if diff > 0 and diff < min_diff:
                min_diff = diff
                next_event = event
                
        # If no events left today, check the first one tomorrow
        if not next_event and self.calendar_events:
            next_event = self.calendar_events[0]
            ev_hour, ev_min = map(int, next_event["time"].split(":"))
            ev_minutes = ev_hour * 60 + ev_min
            min_diff = (24 * 60 - now_minutes) + ev_minutes

        # Calculate stress factor based on meeting proximity
        # Stress starts scaling up 30 minutes before a high-importance meeting
        if next_event:
            importance = next_event["importance"]
            event_type = next_event["type"]
            
            # Base multiplier
            mult = 1.0 if importance == "high" else (0.6 if importance == "medium" else 0.3)
            if event_type == "rest":
                mult = -0.2 # Approaching rest decreases stress
                
            # Proximity function: peak stress at 0 mins to meeting
            if min_diff <= 30:
                proximity_factor = (30.0 - min_diff) / 30.0 # 0.0 to 1.0
                stress = max(0.0, proximity_factor * mult)
            else:
                stress = 0.0
                
            return stress, f"{next_event['title']} at {next_event['time']}"
            
        return 0.0, "No upcoming events"

    def get_context_vector(self) -> Dict[str, Any]:
        """Compiles external context into a single vector."""
        circadian = self.get_circadian_phase()
        cal_stress, next_ev = self.get_calendar_stress()
        
        # Combine parameters
        total_external_stress = max(0.0, min(1.0, circadian["circadian_stress"] + cal_stress))
        
        return {
            "circadian_phase": circadian["phase"],
            "calendar_stress": round(cal_stress, 2),
            "next_event": next_ev,
            "outdoor_weather": f"{self.weather['condition']}, {self.weather['temp']}°C",
            "external_stress_index": round(total_external_stress, 2)
        }
