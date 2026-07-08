# h_sef/config.py
"""
Configuration settings for the Hyper-Personalized Sensory Environment Fabric (H-SEF).
Defines sampling rates, window durations, frequency bands, and system defaults.
"""

# ---- Sampling Rates (Hz) ----
EEG_SAMPLING_RATE = 100    # Hz (Downsampled for efficiency, typical raw is 250+)
PPG_SAMPLING_RATE = 50     # Hz (Sufficient for pulse peak detection)
GSR_SAMPLING_RATE = 10     # Hz (Electrodermal activity changes slowly)
ENV_SAMPLING_RATE = 2      # Hz (Ambient sensors: light, temp, hum)

# ---- Window Sizes (Seconds) ----
EEG_WINDOW_SIZE = 2.0      # Seconds of data required for spectral analysis
PPG_WINDOW_SIZE = 10.0     # Seconds required for reliable HRV (RMSSD) calculation
GSR_WINDOW_SIZE = 5.0      # Seconds for extracting skin conductance tonic/phasic trends

# ---- Signal Processing Constants ----
# EEG Frequency Bands (Hz)
EEG_BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0)
}

# GSR Filters
GSR_LOWPASS_CUTOFF = 0.5   # Hz (To remove high-frequency noise from skin conductance)

import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))
WS_HEARTBEAT_INTERVAL = 1.0 # Seconds between WebSocket updates to frontend

