# h_sef/context/engine.py
"""
Context Engine for H-SEF.
Ingests time of day (circadian rhythms), local weather patterns, and calendar events
to output a contextual stress factor and circadian classification.
Weather is fetched live from the Open-Meteo API (free, no API key required).
"""

import time
import threading
import urllib.request
import urllib.parse
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple

# WMO Weather Interpretation Codes → human-readable label
# https://open-meteo.com/en/docs#weathervariables
WMO_CONDITION_MAP = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Light Showers", 81: "Showers", 82: "Heavy Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Severe Thunderstorm"
}

# WMO code → environmental stress modifier
# (bright/stormy/hot weather can influence indoor comfort targets)
WMO_STRESS_MODIFIER = {
    0: -0.05,  # clear sky = slightly calming
    1: -0.03, 2: 0.0, 3: 0.02,
    45: 0.05, 48: 0.07,
    51: 0.03, 53: 0.05, 55: 0.08,
    61: 0.05, 63: 0.08, 65: 0.12,
    71: 0.05, 73: 0.08, 75: 0.10,
    80: 0.06, 81: 0.09, 82: 0.13,
    95: 0.15, 96: 0.18, 99: 0.20
}


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

        # Default weather — replaced by live fetch when user sets location
        self.weather = {
            "temp": 18.5,
            "condition": "Overcast",
            "humidity": 72,
            "wind_kph": 10.0,
            "wmo_code": 3
        }
        self.location_name = None    # e.g. "London, GB"
        self.location_coords = None  # (lat, lon)
        self._weather_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Live weather fetch via Open-Meteo (free, no API key)
    # ------------------------------------------------------------------

    def update_weather_from_location(self, city: str) -> Dict[str, Any]:
        """
        Geocodes 'city' via Open-Meteo Geocoding API, then fetches
        current weather (temp, humidity, wind, WMO condition) from Open-Meteo.
        Returns a status dict. Safe to call from a background thread.
        """
        try:
            # Step 1: Geocode city name → lat/lon
            geo_url = (
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
            )
            with urllib.request.urlopen(geo_url, timeout=6) as resp:
                geo_data = json.loads(resp.read())

            if not geo_data.get("results"):
                return {"status": "error", "message": f"Location '{city}' not found."}

            result = geo_data["results"][0]
            lat = result["latitude"]
            lon = result["longitude"]
            resolved_name = f"{result['name']}, {result.get('country', '')}"

            # Step 2: Fetch current weather from Open-Meteo
            wx_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
                "&wind_speed_unit=kmh&temperature_unit=celsius&timezone=auto"
            )
            with urllib.request.urlopen(wx_url, timeout=6) as resp:
                wx_data = json.loads(resp.read())

            current = wx_data["current"]
            wmo_code = int(current.get("weather_code", 0))
            condition = WMO_CONDITION_MAP.get(wmo_code, f"Code {wmo_code}")

            with self._weather_lock:
                self.weather = {
                    "temp":      round(float(current["temperature_2m"]), 1),
                    "humidity":  int(current["relative_humidity_2m"]),
                    "wind_kph":  round(float(current["wind_speed_10m"]), 1),
                    "condition": condition,
                    "wmo_code":  wmo_code,
                }
                self.location_name   = resolved_name
                self.location_coords = (lat, lon)

            return {
                "status":   "success",
                "location": resolved_name,
                "weather":  dict(self.weather),
            }

        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_weather_snapshot(self) -> Dict[str, Any]:
        """Thread-safe read of the latest weather state."""
        with self._weather_lock:
            return dict(self.weather)

    def get_weather_stress_modifier(self) -> float:
        """
        Returns an environmental stress modifier based on the current WMO weather code.
        Severe/stormy outdoor conditions increase the system's stress estimate slightly,
        while clear skies provide a mild calming bonus.
        """
        with self._weather_lock:
            code = self.weather.get("wmo_code", 3)
        return WMO_STRESS_MODIFIER.get(code, 0.0)

    # ------------------------------------------------------------------
    # Circadian & Calendar helpers (unchanged logic)
    # ------------------------------------------------------------------

    def get_circadian_phase(self) -> Dict[str, Any]:
        """Classifies the current time into circadian phases."""
        now_dt = datetime.now()
        hour = now_dt.hour

        if 6 <= hour < 11:
            phase = "Morning Activation"
            circadian_stress = 0.1
        elif 11 <= hour < 15:
            phase = "Midday Focus / High Alert"
            circadian_stress = 0.2
        elif 15 <= hour < 18:
            phase = "Afternoon Dip"
            circadian_stress = 0.3
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

        if not next_event and self.calendar_events:
            next_event = self.calendar_events[0]
            ev_hour, ev_min = map(int, next_event["time"].split(":"))
            ev_minutes = ev_hour * 60 + ev_min
            min_diff = (24 * 60 - now_minutes) + ev_minutes

        if next_event:
            importance = next_event["importance"]
            event_type = next_event["type"]
            mult = 1.0 if importance == "high" else (0.6 if importance == "medium" else 0.3)
            if event_type == "rest":
                mult = -0.2
            if min_diff <= 30:
                proximity_factor = (30.0 - min_diff) / 30.0
                stress = max(0.0, proximity_factor * mult)
            else:
                stress = 0.0
            return stress, f"{next_event['title']} at {next_event['time']}"

        return 0.0, "No upcoming events"

    def get_context_vector(self) -> Dict[str, Any]:
        """Compiles external context into a single vector."""
        circadian = self.get_circadian_phase()
        cal_stress, next_ev = self.get_calendar_stress()
        weather_modifier = self.get_weather_stress_modifier()

        with self._weather_lock:
            wx = dict(self.weather)
            loc = self.location_name or "Not set"

        # Weather adds to external stress (e.g. storms → +0.15)
        total_external_stress = max(0.0, min(1.0,
            circadian["circadian_stress"] + cal_stress + weather_modifier
        ))

        return {
            "circadian_phase":      circadian["phase"],
            "calendar_stress":      round(cal_stress, 2),
            "next_event":           next_ev,
            "outdoor_weather":      f"{wx['condition']}, {wx['temp']}°C",
            "outdoor_humidity":     wx["humidity"],
            "outdoor_wind_kph":     wx.get("wind_kph", 0.0),
            "location":             loc,
            "weather_stress_mod":   round(weather_modifier, 3),
            "external_stress_index": round(total_external_stress, 2)
        }
