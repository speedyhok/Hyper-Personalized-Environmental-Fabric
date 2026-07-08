# h_sef/synthesis/generators.py
"""
Generative Sensory Synthesis.
Grounded in biophysical and neuro-entrainment models:
1. Acoustic Binaural Beat parameters: Continuous mapping of carrier and entrainment frequencies
   derived from EEG auditory-evoked response literature (Alpha/Theta vs. Gamma beats).
2. Visual lighting targets: Continuous CCT & Lux mapping matching the Kruithof comfort curve
   and melanopic circadian stimulus scaling.
"""

from typing import Dict, Any

class AcousticSynthesizer:
    @staticmethod
    def synthesize_binaural_parameters(focus_index: float, stress_index: float) -> Dict[str, Any]:
        """
        Calculates optimal carrier and binaural offset frequencies continuously to guide the user's
        brainwave state to Calm (Alpha/Theta) or Focus (Beta/Gamma).
        
        Scientific Grounding:
        - Low carrier frequencies (e.g. 100-150Hz) reduce autonomic arousal (sympathetic tone).
        - Higher carrier frequencies (e.g. 200-250Hz) increase alertness.
        - Entrainment offsets: Alpha (8-12Hz) promotes relaxation, Theta (4-7Hz) restorative sleep,
          and Gamma (38-42Hz) enhances selective attention and working memory.
        """
        # Bounded indices
        f = max(0.0, min(1.0, focus_index))
        s = max(0.0, min(1.0, stress_index))
        
        # 1. Calculate Carrier Frequency (fc) continuously
        carrier = float(max(100.0, min(250.0, 150.0 + 100.0 * f - 50.0 * s)))
        
        # 2. Calculate Binaural Beat frequency (fb) continuously
        if s > 0.4:
            # Shift down to Alpha (10Hz) and down to Theta (6Hz) as stress rises
            # Interpolates between 10Hz and 6Hz
            scale = (s - 0.4) / 0.6
            binaural_freq = float(10.0 - 4.0 * scale)
            sound_type = "Alpha/Theta Entrainment (Stress Reduction)"
        elif f > 0.4:
            # Shift up to Beta (15Hz) and Gamma (40Hz) as focus rises
            # Interpolates between 15Hz and 40Hz
            scale = (f - 0.4) / 0.6
            binaural_freq = float(15.0 + 25.0 * scale)
            sound_type = "Beta/Gamma Entrainment (Cognitive Focus)"
        else:
            # Baseline: Alpha-Beta transition (12Hz)
            binaural_freq = 12.0
            sound_type = "Neutral Sensory Soundscape"
            
        return {
            "carrier_frequency": round(carrier, 1),
            "binaural_offset": round(binaural_freq, 1),
            "sound_type": sound_type
        }

class VisualSynthesizer:
    @staticmethod
    def synthesize_lighting(focus_index: float, stress_index: float) -> Dict[str, Any]:
        """
        Calculates ambient lighting CCT (K) and brightness (Lux) continuously.
        
        Scientific Grounding:
        - Kruithof Curve: Defines the region of visual comfort. Lower illuminance (Lux) requires
          warmer color temperatures (lower CCT) to avoid looking cold/dim, while high illuminance
          requires cooler temperatures (higher CCT) to avoid looking harsh/unpleasant.
        - Circadian Stimulus (CS): Blue-enriched cool light (e.g. 5500-6500K) at high Lux stimulates
          melanopsin-expressing RGCs, suppressing melatonin and enhancing focus. Warm, dim light
          (2000-2700K) minimizes CS, encouraging parasympathetic restoration.
        """
        f = max(0.0, min(1.0, focus_index))
        s = max(0.0, min(1.0, stress_index))
        
        # 1. Calculate Illuminance (Lux) continuously
        # Lux range: 50 Lux (dim/soothing) to 400 Lux (bright task light)
        lux = float(max(50.0, min(400.0, 100.0 + 300.0 * f - 80.0 * s)))
        
        # 2. Calculate Color Temperature (CCT) continuously
        # CCT range: 2000K (very warm amber) to 6000K (cool daylight)
        cct = float(max(2000.0, min(6000.0, 2700.0 + 3300.0 * f - 1000.0 * s)))
        
        # 3. Dynamic RGB color interpolation based on CCT
        # Maps Amber (2000-2700K) -> Soft White (4000K) -> Cool Blueish White (6000K)
        if cct < 4000.0:
            # Interpolate between Amber (253, 186, 116) at 2000K and Natural (254, 243, 199) at 4000K
            t = (cct - 2000.0) / 2000.0
            r = int(253 + (254 - 253) * t)
            g = int(186 + (243 - 186) * t)
            b = int(116 + (199 - 116) * t)
            label = "Warm Calming Glow"
        else:
            # Interpolate between Natural (254, 243, 199) at 4000K and Cool Blue (186, 230, 253) at 6000K
            t = (cct - 4000.0) / 2000.0
            r = int(254 + (186 - 254) * t)
            g = int(243 + (230 - 243) * t)
            b = int(199 + (253 - 199) * t)
            label = "Cool Focus Daylight"
            
        rgb = (r, g, b)
        
        return {
            "cct": int(cct),
            "lux": round(lux, 1),
            "rgb": rgb,
            "rgb_css": f"rgb({r}, {g}, {b})",
            "lighting_label": f"{label} ({int(cct)}K, {round(lux, 1)} Lux)"
        }
