# h_sef/pipeline/stream.py
"""
Simulates real-time multi-modal streaming data for H-SEF, including:
- EEG (electroencephalogram)
- PPG (photoplethysmogram for HRV)
- GSR (galvanic skin response/electrodermal activity)
- Environmental sensors (temperature, ambient light, humidity, decibels)

All streams are modulated by a hidden state (stress, focus) that changes dynamically.
"""

import time
import math
import random
import threading
from typing import Dict, Any, List
import numpy as np

from h_sef.config import (
    EEG_SAMPLING_RATE,
    PPG_SAMPLING_RATE,
    GSR_SAMPLING_RATE,
    ENV_SAMPLING_RATE
)

class BiometricSimulator:
    def __init__(self):
        # Hidden user states (0.0 to 1.0)
        self.stress_level = 0.3
        self.focus_level = 0.5
        
        # Environmental influences
        self.room_temp = 22.0       # Celsius
        self.ambient_light = 300.0   # Lux
        self.ambient_noise = 40.0    # dB
        
        self.running = False
        self._lock = threading.Lock()
        
        # Stream buffers (time, value)
        self.eeg_buffer: List[Dict[str, Any]] = []
        self.ppg_buffer: List[Dict[str, Any]] = []
        self.gsr_buffer: List[Dict[str, Any]] = []
        self.env_buffer: List[Dict[str, Any]] = []
        
        # Keep track of simulation time
        self.start_time = time.time()

    def set_user_state(self, stress: float = None, focus: float = None):
        """Allows external scripts to force-inject stress or focus changes."""
        with self._lock:
            if stress is not None:
                self.stress_level = max(0.0, min(1.0, stress))
            if focus is not None:
                self.focus_level = max(0.0, min(1.0, focus))

    def get_user_state(self) -> Dict[str, float]:
        with self._lock:
            return {"stress": self.stress_level, "focus": self.focus_level}

    def set_environmental_conditions(self, temp: float = None, light: float = None, noise: float = None):
        """Simulates environment changes from actuators or external factors."""
        with self._lock:
            if temp is not None:
                self.room_temp = temp
            if light is not None:
                self.ambient_light = light
            if noise is not None:
                self.ambient_noise = noise

    def start(self):
        self.running = True
        self.start_time = time.time()
        
        # Launch simulator threads
        self.eeg_thread = threading.Thread(target=self._run_eeg, daemon=True)
        self.ppg_thread = threading.Thread(target=self._run_ppg, daemon=True)
        self.gsr_thread = threading.Thread(target=self._run_gsr, daemon=True)
        self.env_thread = threading.Thread(target=self._run_env, daemon=True)
        
        self.eeg_thread.start()
        self.ppg_thread.start()
        self.gsr_thread.start()
        self.env_thread.start()

    def stop(self):
        self.running = False

    def _run_eeg(self):
        """
        Generates simulated EEG containing delta, theta, alpha, beta, and gamma bands.
        Power spectral density is modulated by focus and stress.
        """
        dt = 1.0 / EEG_SAMPLING_RATE
        t = 0.0
        while self.running:
            with self._lock:
                stress = self.stress_level
                focus = self.focus_level
            
            # Base waves
            # Delta (0.5-4 Hz) - High during sleep, low during alert
            a_delta = 10.0 * (1.0 - focus * 0.5)
            # Theta (4-8 Hz) - High during deep focus/cognitive tasks
            a_theta = 5.0 + 8.0 * focus
            # Alpha (8-13 Hz) - High when relaxed, low when stressed/focused
            a_alpha = 15.0 * (1.0 - stress * 0.7) * (1.0 - focus * 0.5)
            # Beta (13-30 Hz) - High during active thinking/stress
            a_beta = 3.0 + 7.0 * stress + 5.0 * focus
            # Gamma (30-45 Hz) - High cognitive integration, high stress
            a_gamma = 1.0 + 4.0 * stress

            # Generate composite wave
            val = (
                a_delta * math.sin(2 * math.pi * 2.0 * t) +
                a_theta * math.sin(2 * math.pi * 6.0 * t) +
                a_alpha * math.sin(2 * math.pi * 10.5 * t) +
                a_beta * math.sin(2 * math.pi * 20.0 * t) +
                a_gamma * math.sin(2 * math.pi * 40.0 * t) +
                random.gauss(0, 3.0)  # Noise
            )
            
            timestamp = time.time()
            # Store in thread-safe buffer
            with self._lock:
                self.eeg_buffer.append({"t": timestamp, "v": val})
                # Cap buffer to last 10 seconds of data (1000 samples)
                if len(self.eeg_buffer) > 1000:
                    self.eeg_buffer.pop(0)
            
            t += dt
            time.sleep(dt)

    def _run_ppg(self):
        """
        Generates simulated PPG pulses. Heart rate is modulated by stress.
        Includes respiratory sinus arrhythmia (RSA) causing HR oscillation at ~0.2 Hz.
        """
        dt = 1.0 / PPG_SAMPLING_RATE
        phase = 0.0
        while self.running:
            with self._lock:
                stress = self.stress_level
            
            # Base Heart Rate in BPM (Stress increases HR)
            base_hr = 60.0 + 40.0 * stress
            # Respiratory Sinus Arrhythmia (modulate HR at ~12 breaths per minute = 0.2 Hz)
            rsa_mod = 5.0 * math.sin(2 * math.pi * 0.2 * time.time())
            hr = base_hr + rsa_mod
            
            # Frequency in Hz
            freq = hr / 60.0
            
            # Synthesize PPG waveform (simulated cardiac pulse using combination of Gaussians)
            # Normal range of phase is 0 to 2*pi
            phase_mod = phase % (2 * math.pi)
            
            # Double peak: Systolic peak and diastolic peak
            systolic = math.exp(-((phase_mod - 1.0) / 0.4) ** 2)
            diastolic = 0.4 * math.exp(-((phase_mod - 2.8) / 0.5) ** 2)
            
            val = systolic + diastolic + random.gauss(0, 0.02)
            
            timestamp = time.time()
            with self._lock:
                self.ppg_buffer.append({"t": timestamp, "v": val})
                if len(self.ppg_buffer) > 500: # Cap at 10 seconds of data
                    self.ppg_buffer.pop(0)
            
            phase += 2 * math.pi * freq * dt
            time.sleep(dt)

    def _run_gsr(self):
        """
        Generates simulated Galvanic Skin Response (electrodermal activity).
        Includes slow moving tonic levels (SCL) and discrete phasic micro-arousals (SCR)
        which occur more frequently when stress is high.
        """
        dt = 1.0 / GSR_SAMPLING_RATE
        
        # Tonic baseline
        tonic_base = 5.0
        
        # Phasic parameters
        scr_activation = 0.0
        scr_decay = 0.95  # Exponential decay coefficient
        
        while self.running:
            with self._lock:
                stress = self.stress_level
            
            # Tonic level rises slowly with stress
            target_tonic = tonic_base + 8.0 * stress
            # Smooth adjustment to target tonic
            tonic_base += (target_tonic - tonic_base) * 0.01
            
            # Trigger phasic SCR events (higher probability under stress)
            # Checked at each sample (10Hz)
            if random.random() < (0.01 + 0.05 * stress):
                # Trigger a skin conductance response
                scr_activation += random.uniform(0.5, 2.0) * (0.5 + 0.5 * stress)
                
            # Decay phasic activation
            scr_activation *= scr_decay
            if scr_activation < 0.01:
                scr_activation = 0.0
                
            # Total GSR (Tonic + Phasic + Noise)
            val = tonic_base + scr_activation + random.gauss(0, 0.05)
            
            timestamp = time.time()
            with self._lock:
                self.gsr_buffer.append({"t": timestamp, "v": val})
                if len(self.gsr_buffer) > 100: # Cap at 10 seconds
                    self.gsr_buffer.pop(0)
            
            time.sleep(dt)

    def _run_env(self):
        """Generates slow environmental trends."""
        dt = 1.0 / ENV_SAMPLING_RATE
        while self.running:
            with self._lock:
                # Add tiny random fluctuations to current targets
                self.room_temp += random.uniform(-0.02, 0.02)
                self.ambient_light = max(10, self.ambient_light + random.uniform(-2, 2))
                self.ambient_noise = max(30, self.ambient_noise + random.uniform(-0.5, 0.5))
                
                temp = self.room_temp
                light = self.ambient_light
                noise = self.ambient_noise
                
            timestamp = time.time()
            with self._lock:
                self.env_buffer.append({
                    "t": timestamp,
                    "temp": temp,
                    "light": light,
                    "noise": noise
                })
                if len(self.env_buffer) > 50: # Cap at 25 seconds
                    self.env_buffer.pop(0)
                    
            time.sleep(dt)

    def pop_eeg(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = list(self.eeg_buffer)
            return data

    def pop_ppg(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = list(self.ppg_buffer)
            return data

    def pop_gsr(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = list(self.gsr_buffer)
            return data

    def pop_env(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = list(self.env_buffer)
            return data
