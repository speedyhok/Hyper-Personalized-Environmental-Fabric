# h_sef/pipeline/wearable_ingest.py
"""
Wearable Ingestion Hub.
Stores real-time health biometrics (Heart Rate, HRV, GSR) posted from
external smartwatches, rings, or bands.
Provides an override lock to swap out simulator data for real-world signals.
"""

import time
from threading import Lock
from typing import Dict, Any

class WearableIngestHub:
    def __init__(self):
        self._lock = Lock()
        self.heart_rate = None
        self.hrv_rmssd = None
        self.gsr = None
        
        self.last_received = 0.0
        self.device_name = "None"

    def register_metrics(
        self,
        heart_rate: float = None,
        hrv_rmssd: float = None,
        gsr: float = None,
        source: str = "Unknown Wearable"
    ):
        """Saves current watch measurements into the buffer with timestamp."""
        with self._lock:
            if heart_rate is not None:
                self.heart_rate = float(heart_rate)
            if hrv_rmssd is not None:
                self.hrv_rmssd = float(hrv_rmssd)
            if gsr is not None:
                self.gsr = float(gsr)
                
            self.last_received = time.time()
            self.device_name = source

    def is_active(self) -> bool:
        """Returns True if smartwatch data was received in the last 45 seconds."""
        with self._lock:
            # Smartwatches usually post updates every 5 to 30 seconds
            return (time.time() - self.last_received) < 45.0

    def get_override_metrics(self) -> Dict[str, Any]:
        """Compiles latest buffered biometrics."""
        with self._lock:
            return {
                "heart_rate": self.heart_rate,
                "hrv_rmssd": self.hrv_rmssd,
                "gsr": self.gsr,
                "source": self.device_name,
                "seconds_since_update": round(time.time() - self.last_received, 1)
            }
