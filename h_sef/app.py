# h_sef/app.py
"""
FastAPI application for H-SEF.
Aggregates the streaming, synchronization, preprocessing, mapping, and context components.
Serves a WebSocket endpoint with real-time analytics and REST endpoints for simulation interaction.
"""

import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import numpy as np
try:
    import torch
except ImportError:
    pass

from h_sef.config import HOST, PORT, WS_HEARTBEAT_INTERVAL
from h_sef.pipeline.stream import BiometricSimulator
from h_sef.pipeline.sync import DataSynchronizer
from h_sef.pipeline.preprocess import SignalPreprocessor
from h_sef.mappings.affect import AffectMapper
from h_sef.context.engine import ContextEngine

# Phase 2 ML Models
from h_sef.models.csm_core import CognitiveStateSequencePredictor, CognitiveStateSpace
from h_sef.models.predictor import InterventionPredictor

# Phase 3 Synthesis & Closed-Loop RL Policy
from h_sef.synthesis.generators import AcousticSynthesizer, VisualSynthesizer
from h_sef.synthesis.olfactory import OlfactoryDispersionEngine
from h_sef.synthesis.policy import ClosedLoopRLPolicy

app = FastAPI(title="Hyper-Personalized Sensory Environment Fabric (H-SEF)")

# Initialize pipeline modules
simulator = BiometricSimulator()
preprocessor = SignalPreprocessor()
mapper = AffectMapper()
context_engine = ContextEngine()

# Initialize ML Models
csm_predictor = CognitiveStateSequencePredictor()
intervention_predictor = InterventionPredictor()

# Initialize Phase 3 Generators & Policies
acoustic_synth = AcousticSynthesizer()
visual_synth = VisualSynthesizer()
olfactory_engine = OlfactoryDispersionEngine()
rl_policy = ClosedLoopRLPolicy(target_state="Focus")

# Phase 4 Orchestrator
from h_sef.orchestrator import HSEFOrchestrator
orchestrator = HSEFOrchestrator(csm_predictor, intervention_predictor, rl_policy, context_engine)

# Phase 5 Hardware Connectors & Ingestion
import json
from h_sef.pipeline.wearable_ingest import WearableIngestHub
wearable_hub = WearableIngestHub()

# Start simulator on startup
@app.on_event("startup")
def startup_event():
    simulator.start()
    # Load hardware config if exists
    try:
        if os.path.exists("config/hardware_config.json"):
            with open("config/hardware_config.json", "r") as f:
                cfg = json.load(f)
                orchestrator.configure_hardware(
                    hue_ip=cfg.get("hue_ip"),
                    hue_key=cfg.get("hue_key"),
                    ha_url=cfg.get("ha_url"),
                    ha_token=cfg.get("ha_token")
                )
    except Exception:
        pass

@app.on_event("shutdown")
def shutdown_event():
    simulator.stop()

# Define API models for simulation controls
class StressorInput(BaseModel):
    stress: float = None
    focus: float = None

class ActuatorOverride(BaseModel):
    temp: float = None
    light: float = None
    noise: float = None

class TargetStateInput(BaseModel):
    target: str # "Focus" or "Calm"

@app.post("/api/target_state")
def set_target_state(data: TargetStateInput):
    """Dynamically changes the RL agent's target state optimization goals."""
    if data.target in ["Focus", "Calm"]:
        rl_policy.target_state = data.target
        rl_policy.target_arousal = 0.4 if data.target == "Focus" else -0.6
        return {"status": "success", "target_state": rl_policy.target_state}
    return {"status": "error", "message": "Invalid target state"}


# ---- Location & Live Weather Endpoints ----

class LocationInput(BaseModel):
    city: str

@app.post("/api/location")
def set_location(data: LocationInput):
    """
    Geocodes the given city name and fetches live weather from Open-Meteo.
    Runs synchronously (fast enough for a REST call; ~200-500ms).
    """
    result = context_engine.update_weather_from_location(data.city.strip())
    return result

@app.get("/api/location")
def get_location():
    """Returns the current location and live weather snapshot."""
    wx = context_engine.get_weather_snapshot()
    return {
        "location": context_engine.location_name or "Not set",
        "weather":  wx
    }


# Define API models for Phase 5 Hardware
class WearableIngestInput(BaseModel):
    heart_rate: float = None
    hrv_rmssd: float = None
    gsr: float = None
    source: str = "Smartwatch"

class HardwareConfigInput(BaseModel):
    hue_ip: str = None
    hue_key: str = None
    ha_url: str = None
    ha_token: str = None

@app.post("/api/wearable/ingest")
def ingest_wearable_data(data: dict):
    """Ingests smartwatch biometric data (from direct JSON or Sensor Logger) and overrides simulation."""
    print(f"[DEBUG INGEST] Received payload keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    
    heart_rate = None
    hrv_rmssd = None
    gsr = None
    source = "Smartwatch"

    if isinstance(data, dict) and "payload" in data and isinstance(data["payload"], list):
        source = data.get("deviceId", "Sensor Logger")
        print(f"[DEBUG INGEST] Sensor Logger payload length: {len(data['payload'])}, sensors: {[x.get('name') for x in data['payload'] if isinstance(x, dict)]}")
        
        for item in data["payload"]:
            if not isinstance(item, dict):
                continue
            name_raw = item.get("name", "")
            name = name_raw.lower().replace("_", "").replace(" ", "")
            values = item.get("values", {})
            if not isinstance(values, dict):
                continue
            
            if name == "heartrate":
                heart_rate = values.get("bpm") or values.get("value")
            elif name in ("hrv", "hrvrmssd", "rmssd"):
                hrv_rmssd = values.get("value") or values.get("ms")
            elif name in ("gsr", "skinconductance", "eda", "electrodermalactivity"):
                gsr = values.get("value") or values.get("us") or values.get("uS")
    elif isinstance(data, dict):
        # Direct key-value format
        heart_rate = data.get("heart_rate") or data.get("heartRate")
        hrv_rmssd = data.get("hrv_rmssd") or data.get("hrvRmssd")

        gsr = data.get("gsr")
        source = data.get("source", "Smartwatch")

    if heart_rate is not None or hrv_rmssd is not None or gsr is not None:
        wearable_hub.register_metrics(
            heart_rate=heart_rate,
            hrv_rmssd=hrv_rmssd,
            gsr=gsr,
            source=source
        )
        return {
            "status": "success", 
            "override_active": wearable_hub.is_active(), 
            "received": {"hr": heart_rate, "hrv": hrv_rmssd, "gsr": gsr}
        }
    
    return {"status": "ignored", "reason": "No relevant biometric data found in payload"}


@app.post("/api/config/hardware")
def save_hardware_config(data: HardwareConfigInput):
    """Saves Hue/HA credentials and updates orchestrator clients."""
    hue_ip = data.hue_ip if data.hue_ip else None
    hue_key = data.hue_key if data.hue_key else None
    ha_url = data.ha_url if data.ha_url else None
    ha_token = data.ha_token if data.ha_token else None
    
    orchestrator.configure_hardware(
        hue_ip=hue_ip,
        hue_key=hue_key,
        ha_url=ha_url,
        ha_token=ha_token
    )
    
    os.makedirs("config", exist_ok=True)
    with open("config/hardware_config.json", "w") as f:
        json.dump({
            "hue_ip": hue_ip,
            "hue_key": hue_key,
            "ha_url": ha_url,
            "ha_token": ha_token
        }, f)
        
    return {
        "status": "success",
        "hue_configured": orchestrator.hue.is_configured(),
        "ha_configured": orchestrator.ha.is_configured()
    }

@app.get("/api/config/hardware")
def get_hardware_config():
    """Retrieves active configuration statuses (hiding tokens)."""
    return {
        "hue_ip": orchestrator.hue.ip or "",
        "hue_key_configured": bool(orchestrator.hue.app_key),
        "ha_url": orchestrator.ha.base_url or "",
        "ha_token_configured": bool(orchestrator.ha.token)
    }

@app.post("/api/stressor")
def trigger_stressor(data: StressorInput):
    """Allows manual injection of cognitive load or stress state for demonstration."""
    simulator.set_user_state(stress=data.stress, focus=data.focus)
    return {"status": "success", "state": simulator.get_user_state()}

class FeedbackInput(BaseModel):
    rating: int # +1 (thumbs up), -1 (thumbs down)

@app.post("/api/feedback")
def submit_feedback(data: FeedbackInput):
    """Allows user reinforcement feedback to modify RL training updates."""
    # Thumbs down increases exploration for new states; thumbs up solidifies actions
    if data.rating == -1:
        rl_policy.epsilon = min(0.5, rl_policy.epsilon + 0.05)
    else:
        rl_policy.epsilon = max(0.02, rl_policy.epsilon - 0.02)
    return {"status": "feedback_received", "epsilon": rl_policy.epsilon}

@app.post("/api/actuator")
def override_actuator(data: ActuatorOverride):
    """Overrides environmental conditions to simulate actuator operations."""
    simulator.set_environmental_conditions(temp=data.temp, light=data.light, noise=data.noise)
    
    # Phase 4 Safety Lockouts: Manual adjustments block automated control
    if data.temp is not None:
        orchestrator.safety.register_manual_override("climate")
    if data.light is not None:
        orchestrator.safety.register_manual_override("lighting")
        
    # Induce physiological changes in response to actuator (closed-loop simulation)
    # E.g. Lowering temp and noise reduces stress. Dimming light helps focus.
    current_state = simulator.get_user_state()
    new_stress = current_state["stress"]
    new_focus = current_state["focus"]
    
    if data.temp is not None:
        # Ideal temp is 21C. Higher temps increase stress.
        temp_diff = abs(data.temp - 21.0)
        new_stress += (temp_diff * 0.05 - 0.1) # Cool temp relaxes, high temp stresses
    if data.light is not None:
        # Dim light (focused working) vs harsh bright light
        if data.light < 150: # Calm, low alert
            new_stress -= 0.1
        elif 150 <= data.light < 400: # Focused focus
            new_focus += 0.1
            new_stress -= 0.05
        else: # High alert/harsh
            new_stress += 0.1
            
    # Bound states
    new_stress = max(0.0, min(1.0, new_stress))
    new_focus = max(0.0, min(1.0, new_focus))
    simulator.set_user_state(stress=new_stress, focus=new_focus)
    
    return {
        "status": "actuator_applied",
        "room_state": {
            "temp": simulator.room_temp,
            "light": simulator.ambient_light,
            "noise": simulator.ambient_noise
        },
        "user_state": {"stress": new_stress, "focus": new_focus}
    }

# Mount static files for dashboard HTML/CSS/JS
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def get_index():
    """Redirects to static dashboard index.html."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("Dashboard index.html not found. Place it under static/ directory.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 1. Fetch raw streams
            eeg_raw = simulator.pop_eeg()
            ppg_raw = simulator.pop_ppg()
            gsr_raw = simulator.pop_gsr()
            env_raw = simulator.pop_env()
            
            # 2. Cross-modal synchronization
            timestamps, aligned = DataSynchronizer.synchronize(
                eeg_raw, ppg_raw, gsr_raw, env_raw, target_hz=50.0, window_seconds=4.0
            )
            
            if len(timestamps) > 0:
                # 3. Preprocess and extract features
                eeg_features = preprocessor.process_eeg(aligned["eeg"])
                ppg_features = preprocessor.process_ppg(aligned["ppg"])
                gsr_features = preprocessor.process_gsr(aligned["gsr"])
                
                # Phase 5: Smartwatch real-time biometric override ingestion
                if wearable_hub.is_active():
                    override = wearable_hub.get_override_metrics()
                    if override["heart_rate"] is not None:
                        ppg_features["hr"] = override["heart_rate"]
                    if override["hrv_rmssd"] is not None:
                        ppg_features["rmssd"] = override["hrv_rmssd"]
                    if override["gsr"] is not None:
                        gsr_features["phasic"] = override["gsr"]
                
                # 4. Map features to cognitive and affective states
                csm_state = mapper.compute_cognitive_state(eeg_features, ppg_features, gsr_features)
                
                # 5. Get external context
                context = context_engine.get_context_vector()
                
                # 6. Generate closed-loop actuator recommendations (Pre-Phase 3 demonstration)
                # Light spectrum and intensity recommendation
                if csm_state["stress_index"] > 0.6:
                    rec_light = "Warm Amber (2700K), 120 Lux"
                    rec_sound = "Pink Noise + 10Hz Binaural Beats (Relaxation)"
                    rec_temp = "21.0 °C (Cooling)"
                    rec_scent = "Lavender / Linalool (Anxiolytic)"
                elif csm_state["focus_index"] > 0.5:
                    rec_light = "Cool Daylight (5500K), 350 Lux"
                    rec_sound = "Brownian Noise + 40Hz Binaural Beats (Gamma/Focus)"
                    rec_temp = "21.5 °C"
                    rec_scent = "Peppermint / Limonene (Cognitive stimulant)"
                else:
                    rec_light = "Natural White (4000K), 250 Lux"
                    rec_sound = "Ambient Nature Soundscape"
                    rec_temp = "22.0 °C"
                    rec_scent = "Neutral / Fresh Air"

                # 7. Construct sequence matrix for ML modeling (Shape: [seq_len, 11])
                seq_len = len(aligned["eeg"])
                seq_matrix = np.stack([
                    aligned["eeg"],
                    aligned["eeg"] * 0.5, # beta wave estimator
                    aligned["eeg"] * 0.2, # theta wave estimator
                    aligned["ppg"],
                    aligned["ppg"] * 0.1, # hrv peak estimator
                    aligned["gsr"],
                    aligned["gsr"] * 0.05, # phasic transient estimator
                    aligned["room_temp"],
                    aligned["ambient_light"],
                    aligned["ambient_noise"],
                    np.full(seq_len, context["external_stress_index"])
                ], axis=1)
                
                # 8. Causal attribution (Saliency mapping)
                causal_attr = csm_predictor.calculate_causal_attribution(seq_matrix)
                
                # 9. Predict future user states (PyTorch LSTM forward inference fallback to NumPy)
                from h_sef.models.csm_core import HAS_TORCH
                if HAS_TORCH:
                    with torch.no_grad():
                        seq_tensor = torch.tensor(seq_matrix, dtype=torch.float32).unsqueeze(0)
                        pred_out = csm_predictor(seq_tensor)[0].numpy()
                else:
                    pred_out = csm_predictor.predict_numpy(seq_matrix)
                    
                pred_v = float(np.clip(csm_state["valence"] + pred_out[0]*0.1, -1.0, 1.0))
                pred_a = float(np.clip(csm_state["arousal"] + pred_out[1]*0.1, -1.0, 1.0))
                pred_cl = float(np.clip(csm_state["cognitive_load"] + pred_out[2]*0.05, 0.0, 1.0))
                    
                # 10. Generate interpolated transition paths
                start_coord = (csm_state["valence"], csm_state["arousal"])
                end_coord = (pred_v, pred_a)
                interpolated_path = CognitiveStateSpace.interpolate_path(start_coord, end_coord, steps=8)
                
                # 11. Run predictive intervention outcomes (Scikit-Learn Ridge)
                # Predict what happens if H-SEF cools room (-1.5C), dims light (-150 Lux), dampens noise (-8dB)
                predicted_outcome = intervention_predictor.predict_outcome(
                    csm_state, delta_temp=-1.5, delta_light=-150.0, delta_noise=-8.0
                )

                # 12. Run Phase 3 Generative Synthesis Model mappings
                synthesized_light = visual_synth.synthesize_lighting(csm_state["focus_index"], csm_state["stress_index"])
                synthesized_sound = acoustic_synth.synthesize_binaural_parameters(csm_state["focus_index"], csm_state["stress_index"])
                
                scent_type = "Lavender / Linalool (Anxiolytic)" if csm_state["stress_index"] > 0.6 else (
                    "Peppermint / Limonene (Cognitive Stimulant)" if csm_state["focus_index"] > 0.5 else "Neutral Air"
                )
                scent_dispersion = olfactory_engine.simulate_scent_dispersion(
                    distance_meters=2.0, wind_velocity_mps=0.4, scent_type=scent_type
                )
                
                # 13. Closed-Loop Reinforcement Learning optimization step
                rl_action_idx, rl_action_label = rl_policy.select_action(
                    csm_state["valence"], csm_state["arousal"], csm_state["cognitive_load"]
                )
                
                # Execute RL Action inside Simulator (adjusting environment parameters dynamically)
                if rl_action_idx == 0:  # Cool Room
                    simulator.set_environmental_conditions(temp=max(18.0, simulator.room_temp - 0.1))
                elif rl_action_idx == 1:  # Warm Room
                    simulator.set_environmental_conditions(temp=min(26.0, simulator.room_temp + 0.1))
                elif rl_action_idx == 2:  # Dim Lights
                    simulator.set_environmental_conditions(light=max(40, simulator.ambient_light - 10))
                elif rl_action_idx == 3:  # Brighten Lights
                    simulator.set_environmental_conditions(light=min(500, simulator.ambient_light + 10))
                # Note: Actions 4 & 5 (Beats) are managed digitally by the Synthesizer
                
                # Q-learning reward evaluation
                rl_reward = rl_policy.compute_reward(csm_state["valence"], csm_state["arousal"], rl_action_idx)
                next_state_est = {
                    "valence": predicted_outcome["predicted_valence"],
                    "arousal": predicted_outcome["predicted_arousal"],
                    "cognitive_load": predicted_outcome["predicted_cognitive_load"]
                }
                rl_policy.update_q_value(csm_state, rl_action_idx, rl_reward, next_state_est)

                # 14. Execute control cycle on standardized physical actuators (Phase 4 integration)
                actuator_logs = orchestrator.execute_control_cycle(csm_state, predicted_outcome, rl_action_idx, {
                    "light": synthesized_light,
                    "sound": synthesized_sound,
                    "olfactory": scent_dispersion
                })

                # Send synchronized package to client
                package = {
                    "time": time_dict_list(timestamps)[-1] if len(timestamps) > 0 else 0,
                    # High-frequency waveforms for dashboard charting (downsampled for performance)
                    "signals": {
                        "eeg": aligned["eeg"][-100:].tolist(),  # Last 2s
                        "ppg": aligned["ppg"][-100:].tolist(),
                        "gsr": aligned["gsr"][-100:].tolist()
                    },
                    "features": {
                        "heart_rate": ppg_features["hr"],
                        "hrv_rmssd": ppg_features["rmssd"],
                        "gsr_tonic": gsr_features["tonic"],
                        "gsr_phasic": gsr_features["phasic"],
                        "eeg_alpha": eeg_features["alpha"],
                        "eeg_beta": eeg_features["beta"],
                        "eeg_theta": eeg_features["theta"]
                    },
                    "csm": csm_state,
                    "context": context,
                    "environment": {
                        "temp": round(aligned["room_temp"][-1], 2),
                        "light": round(aligned["ambient_light"][-1], 1),
                        "noise": round(aligned["ambient_noise"][-1], 1)
                    },
                    "recommendations": {
                        "light": rec_light,
                        "sound": rec_sound,
                        "temp": rec_temp,
                        "scent": rec_scent
                    },
                    # New Phase 2 Machine Learning Outputs
                    "csm_predictions": {
                        "valence": round(pred_v, 3),
                        "arousal": round(pred_a, 3),
                        "cognitive_load": round(pred_cl, 3),
                        "stress_index": round(max(0.0, min(1.0, (pred_a - pred_v)/2.0)), 3),
                        "interpolated_path": interpolated_path
                    },
                    "causal_attribution": causal_attr,
                    "predicted_outcome": predicted_outcome,
                    
                    # New Phase 3 Generative Sensory Synthesis & RL Outputs
                    "synthesis": {
                        "light": synthesized_light,
                        "sound": synthesized_sound,
                        "olfactory": scent_dispersion
                    },
                    "rl_policy": {
                        "action": rl_action_label,
                        "reward": round(rl_reward, 3),
                        "target_state": rl_policy.target_state
                    },
                    
                    # New Phase 4 Safety & Actuator Output logs
                    "safety": orchestrator.safety.get_lockout_status(),
                    "hardware_logs": [item["log"] for item in actuator_logs],
                    
                    # New Phase 5 Wearable Status Override logs
                    "wearable": wearable_hub.get_override_metrics(),
                    "hue_connected": orchestrator.hue.is_configured(),
                    "ha_connected": orchestrator.ha.is_configured()
                }
                await websocket.send_json(package)
                
            await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Silently log errors or handle disconnecting
        pass

def time_dict_list(arr) -> list:
    return [float(x) for x in arr]
