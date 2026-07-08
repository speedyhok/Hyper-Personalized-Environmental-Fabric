# h_sef/pipeline/sync.py
"""
Handles cross-modal synchronization of signals with different sampling rates.
Resamples raw queues of EEG (100Hz), PPG (50Hz), and GSR (10Hz) to a unified timeline
using numpy interpolation, accounting for temporal misalignment and clock drift.
"""

from typing import List, Dict, Any, Tuple
import numpy as np

class DataSynchronizer:
    @staticmethod
    def synchronize(
        eeg_raw: List[Dict[str, Any]],
        ppg_raw: List[Dict[str, Any]],
        gsr_raw: List[Dict[str, Any]],
        env_raw: List[Dict[str, Any]],
        target_hz: float = 50.0,
        window_seconds: float = 2.0
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Synchronizes all incoming data streams by resampling them to a uniform time grid
        for the most recent 'window_seconds' period.
        
        Returns:
            timestamps: np.ndarray (shape: [N]) of resampled time ticks.
            aligned_data: Dict mapping sensor names to np.ndarray of shape [N].
        """
        # Ensure we have data in all streams to synchronize
        if not eeg_raw or not ppg_raw or not gsr_raw or not env_raw:
            return np.array([]), {}
            
        # Determine the time boundaries based on the latest available data
        now = max(eeg_raw[-1]["t"], ppg_raw[-1]["t"], gsr_raw[-1]["t"], env_raw[-1]["t"])
        start_time = now - window_seconds
        
        # Create a uniform time grid
        num_samples = int(window_seconds * target_hz)
        timestamps = np.linspace(start_time, now, num_samples)
        
        # Helper to extract time and values
        def get_t_v(raw_data: List[Dict[str, Any]], key: str = "v") -> Tuple[np.ndarray, np.ndarray]:
            t = np.array([item["t"] for item in raw_data])
            # If environmental data, key might be different (e.g. temp, light, noise)
            v = np.array([item[key] for item in raw_data])
            return t, v

        # Extract times and values
        eeg_t, eeg_v = get_t_v(eeg_raw)
        ppg_t, ppg_v = get_t_v(ppg_raw)
        gsr_t, gsr_v = get_t_v(gsr_raw)
        
        env_t = np.array([item["t"] for item in env_raw])
        env_temp = np.array([item["temp"] for item in env_raw])
        env_light = np.array([item["light"] for item in env_raw])
        env_noise = np.array([item["noise"] for item in env_raw])

        # Interopolate onto the uniform grid
        # numpy.interp handles values outside the range by setting them to the boundary values (left/right)
        eeg_sync = np.interp(timestamps, eeg_t, eeg_v)
        ppg_sync = np.interp(timestamps, ppg_t, ppg_v)
        gsr_sync = np.interp(timestamps, gsr_t, gsr_v)
        
        temp_sync = np.interp(timestamps, env_t, env_temp)
        light_sync = np.interp(timestamps, env_t, env_light)
        noise_sync = np.interp(timestamps, env_t, env_noise)

        aligned_data = {
            "eeg": eeg_sync,
            "ppg": ppg_sync,
            "gsr": gsr_sync,
            "room_temp": temp_sync,
            "ambient_light": light_sync,
            "ambient_noise": noise_sync
        }

        return timestamps, aligned_data
