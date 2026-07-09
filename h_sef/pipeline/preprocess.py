# h_sef/pipeline/preprocess.py
"""
Signal preprocessing algorithms for H-SEF.
Includes:
- EEG bandpower extraction (using Scipy Welch or FFT)
- PPG peak detection and Heart Rate Variability (HRV) RMSSD calculation
- GSR filtration and Tonic/Phasic signal decomposition
"""

from typing import Dict, Any, List, Tuple
import numpy as np
import scipy.signal as signal

from h_sef.config import EEG_BANDS, GSR_LOWPASS_CUTOFF

class SignalPreprocessor:
    def __init__(self, target_hz: float = 50.0):
        self.target_hz = target_hz
        
        # Design a Butterworth low-pass filter for GSR
        nyquist = 0.5 * target_hz
        normal_cutoff = GSR_LOWPASS_CUTOFF / nyquist
        # 2nd order butterworth
        self.b_gsr, self.a_gsr = signal.butter(2, normal_cutoff, btype='low', analog=False)
        
        # History buffers for smoothing (EMA filters to prevent rapid simulated data jitter)
        self.ema_hr = None
        self.ema_rmssd = None
        self.ema_tonic = None
        self.ema_phasic = None
        self.ema_eeg = {}

    def process_eeg(self, eeg_signal: np.ndarray) -> Dict[str, float]:
        """
        Computes Power Spectral Density (PSD) using Welch's method and returns
        relative power for Delta, Theta, Alpha, Beta, and Gamma bands.
        """
        if len(eeg_signal) < 16:
            return {band: 0.0 for band in EEG_BANDS}

        # Compute power spectral density
        # Adjust nperseg to fit the window size (e.g. 100 samples)
        nperseg = min(len(eeg_signal), 128)
        freqs, psd = signal.welch(eeg_signal, fs=self.target_hz, nperseg=nperseg)

        band_powers = {}
        total_power = 1e-10  # Prevent division by zero

        for band, (low, high) in EEG_BANDS.items():
            # Find indices of frequencies in the band
            idx = np.where((freqs >= low) & (freqs <= high))[0]
            if len(idx) > 0:
                # Integrate the power spectral density
                power = np.trapezoid(psd[idx], freqs[idx])
            else:
                power = 0.0
            band_powers[band] = power
            total_power += power

        # Calculate relative power (proportions)
        relative_powers = {}
        for band, power in band_powers.items():
            val = float(power / total_power)
            # Apply EMA smoothing to the relative power to prevent rapid jumping
            if band not in self.ema_eeg:
                self.ema_eeg[band] = val
            else:
                self.ema_eeg[band] = 0.05 * val + 0.95 * self.ema_eeg[band]
            relative_powers[band] = self.ema_eeg[band]

        return relative_powers

    def process_ppg(self, ppg_signal: np.ndarray) -> Dict[str, float]:
        """
        Detects heartbeats (systolic peaks) in the PPG signal, calculates
        instantaneous Heart Rate (HR) and Heart Rate Variability (HRV) using RMSSD.
        """
        # Default fallback values
        features = {"hr": 70.0, "rmssd": 40.0}
        
        if len(ppg_signal) < 30:
            return features

        # Normalize the signal to improve peak detection
        sig_min, sig_max = np.min(ppg_signal), np.max(ppg_signal)
        if sig_max - sig_min < 1e-5:
            return features
        norm_sig = (ppg_signal - sig_min) / (sig_max - sig_min)

        # Simple peak detection: find peaks that are at least 0.5s apart (Nyquist-ish for high HR)
        # 50 Hz * 0.5 seconds = 25 samples minimum distance
        min_dist = int(0.4 * self.target_hz)
        
        # We find peaks that rise above 0.4 height
        peaks, _ = signal.find_peaks(norm_sig, distance=min_dist, height=0.4)

        if len(peaks) < 2:
            return features

        # Peak timestamps in seconds
        peak_times = peaks / self.target_hz
        
        # Calculate Peak-to-Peak (RR) intervals in milliseconds
        rr_intervals = np.diff(peak_times) * 1000.0  # ms
        
        # Calculate instantaneous HR from the last interval
        last_rr = rr_intervals[-1]
        hr = 60000.0 / last_rr if last_rr > 0 else 70.0
        
        # Calculate RMSSD: Root Mean Square of Successive Differences
        if len(rr_intervals) >= 2:
            diffs = np.diff(rr_intervals)
            rmssd = np.sqrt(np.mean(diffs ** 2))
        else:
            rmssd = 40.0 # Normal default
            
        hr_clipped = float(np.clip(hr, 40.0, 180.0))
        rmssd_clipped = float(np.clip(rmssd, 5.0, 150.0))
        
        # Apply exponential moving average (EMA) smoothing to stabilize values
        if self.ema_hr is None:
            self.ema_hr = hr_clipped
        else:
            self.ema_hr = 0.03 * hr_clipped + 0.97 * self.ema_hr
            
        if self.ema_rmssd is None:
            self.ema_rmssd = rmssd_clipped
        else:
            self.ema_rmssd = 0.03 * rmssd_clipped + 0.97 * self.ema_rmssd
            
        features["hr"] = self.ema_hr
        features["rmssd"] = self.ema_rmssd
        
        return features

    def process_gsr(self, gsr_signal: np.ndarray) -> Dict[str, float]:
        """
        Filters raw GSR signal and decomposes it into Tonic (baseline SCL)
        and Phasic (rapid SCR) components.
        """
        if len(gsr_signal) < 10:
            return {"gsr_clean": 5.0, "tonic": 5.0, "phasic": 0.0}

        # Apply lowpass filter to remove high frequency noise
        # Using filtfilt to avoid phase shift if signal is long enough, otherwise lfilter
        if len(gsr_signal) > 6:
            clean_gsr = signal.filtfilt(self.b_gsr, self.a_gsr, gsr_signal)
        else:
            clean_gsr = signal.lfilter(self.b_gsr, self.a_gsr, gsr_signal)

        # Tonic estimation: very slow moving average or median filter
        # A 4-second median filter works well to capture baseline SCL
        kernel_size = int(4.0 * self.target_hz)
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        # Cap kernel size to signal length
        kernel_size = min(kernel_size, len(clean_gsr))
        if kernel_size % 2 == 0:
            kernel_size -= 1
        
        if kernel_size > 2:
            tonic = signal.medfilt(clean_gsr, kernel_size=kernel_size)
        else:
            tonic = clean_gsr

        # Phasic is clean_gsr minus tonic baseline
        phasic = clean_gsr - tonic
        
        # Take the root mean square or max phasic amplitude in the current window
        phasic_strength = float(np.max(np.abs(phasic)))

        t_val = float(tonic[-1])
        p_val = float(phasic_strength)
        
        # Apply EMA smoothing to stabilize SCL/SCR values
        if self.ema_tonic is None:
            self.ema_tonic = t_val
        else:
            self.ema_tonic = 0.02 * t_val + 0.98 * self.ema_tonic
            
        if self.ema_phasic is None:
            self.ema_phasic = p_val
        else:
            self.ema_phasic = 0.04 * p_val + 0.96 * self.ema_phasic

        return {
            "gsr_clean": float(clean_gsr[-1]),
            "tonic": self.ema_tonic,
            "phasic": self.ema_phasic
        }
