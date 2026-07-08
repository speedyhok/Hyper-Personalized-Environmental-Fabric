# h_sef/synthesis/olfactory.py
"""
Olfactory Dispersion Engine.
Grounded in fluid-dynamics transport principles:
Models volatile organic compound (VOC) transport using the 1D convection-diffusion
partial differential equation (PDE) with indoor turbulent eddy diffusivity:
dC/dt + u * dC/dx = D_eff * d2C/dx2
"""

import math
import time
from typing import Dict, Any

class OlfactoryDispersionEngine:
    def __init__(self):
        # Mechanical device release lag (seconds)
        self.device_startup_lag = 1.0
        
        # State tracking for continuous real-time transport simulation
        self.last_scent = "Neutral"
        self.release_time = time.time()
        self.source_mass = 1.5 # Arbitrary mass scalar for normalization

    def simulate_scent_dispersion(
        self,
        distance_meters: float = 2.0,
        wind_velocity_mps: float = 0.4, # Fan velocity in m/s
        scent_type: str = "Neutral"
    ) -> Dict[str, Any]:
        """
        Calculates local VOC concentration at distance x and elapsed time t.
        
        Scientific Grounding:
        - Uses the closed-form analytical solution of the 1D convection-diffusion equation
          for a point source release:
          C(x, t) = (M / sqrt(4 * pi * D_eff * t)) * exp( - (x - u * t)^2 / (4 * D_eff * t) )
        - u is the fan velocity (advection speed).
        - D_eff is the effective indoor turbulent eddy diffusion coefficient (eddy diffusivity),
          which is several orders of magnitude larger than molecular diffusivity (10^-2 vs 10^-6 m^2/s)
          due to indoor air currents.
        """
        current_time = time.time()
        
        # Detect scent change and reset dispersion stopwatch
        if scent_type != self.last_scent:
            self.last_scent = scent_type
            self.release_time = current_time

        # If neutral air is selected, scent concentration naturally washes out to zero
        if "Neutral" in scent_type:
            return {
                "scent": "Neutral Air",
                "transport_latency_seconds": 0.0,
                "estimated_peak_intensity_pct": 0.0,
                "decay_rate_per_sec": 0.0,
                "dispersion_status": "Ventilated"
            }

        # Calculate transport time elapsed since scent release
        # Subtract device mechanical startup lag
        elapsed = current_time - self.release_time - self.device_startup_lag
        
        # 1. Choose turbulent eddy diffusion coefficient Deff based on molecular properties
        # Lavender (Linalool, MW: 154.25) vs. Peppermint (Menthol, MW: 156.27)
        if "Lavender" in scent_type:
            d_eff = 0.08  # m^2/s (high volatility)
            decay_coef = 0.08
        elif "Peppermint" in scent_type:
            d_eff = 0.10  # m^2/s (menthol, fast dispersion)
            decay_coef = 0.12
        else:
            d_eff = 0.06  # default
            decay_coef = 0.05

        # Bounded advection speed
        u = max(0.1, wind_velocity_mps)
        x = max(0.5, distance_meters)
        
        if elapsed <= 0.0:
            # Scent has not left the nozzle or startup lag is active
            return {
                "scent": scent_type,
                "transport_latency_seconds": round(x / u + self.device_startup_lag, 2),
                "estimated_peak_intensity_pct": 0.0,
                "decay_rate_per_sec": decay_coef,
                "dispersion_status": "Venting Lag"
            }

        # 2. Convection-diffusion equation analytical solver
        # Calculate denominator with Deff
        denom = 4.0 * math.pi * d_eff * elapsed
        sqrt_denom = math.sqrt(denom)
        
        # Calculate advection exponent: (x - u * t)^2 / (4 * D_eff * t)
        numerator = (x - u * elapsed) ** 2
        four_d_t = 4.0 * d_eff * elapsed
        exponent = -numerator / four_d_t
        
        # Compute concentration C(x, t)
        c_raw = (self.source_mass / sqrt_denom) * math.exp(exponent)
        
        # Normalize concentration to a percentage intensity scale (capped at 100%)
        # Peak of analytical solution occurs when x = u * t, where C = M / sqrt(4 * pi * Deff * t)
        # At x=2, u=0.4, t_peak=5s. Peak concentration is approx M / sqrt(4*pi*0.08*5) = M / 2.24
        # We scale peak concentration to be around 90-100%
        intensity = min(100.0, c_raw * 120.0)
        
        # Status threshold
        if intensity < 5.0:
            status = "Approaching" if (u * elapsed < x) else "Fading"
        elif intensity < 50.0:
            status = "Arriving" if (u * elapsed < x) else "Lingering"
        else:
            status = "Peak Concentration"

        return {
            "scent": scent_type,
            "transport_latency_seconds": round(x / u + self.device_startup_lag, 2),
            "estimated_peak_intensity_pct": round(intensity, 1),
            "decay_rate_per_sec": decay_coef,
            "dispersion_status": status
        }
