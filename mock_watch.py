import time
import requests
import math
import random

url = "http://127.0.0.1:8000/api/wearable/ingest"
print("Starting mock smartwatch stream... Press CTRL+C to stop.")

t = 0
try:
    while True:
        # Generate naturally fluctuating biometrics
        hr = round(78.0 + 8.0 * math.sin(t * 0.15) + random.uniform(-1, 1), 1)
        hrv = round(48.0 - 5.0 * math.sin(t * 0.15) + random.uniform(-2, 2), 1)
        gsr = round(5.5 + 1.2 * math.cos(t * 0.1) + random.uniform(-0.1, 0.1), 2)
        
        payload = {
            "heart_rate": hr,
            "hrv_rmssd": hrv,
            "gsr": gsr,
            "source": "Smartwatch (Mock)"
        }
        
        try:
            r = requests.post(url, json=payload, timeout=2.0)
            if r.status_code == 200:
                print(f"Ingested -> HR: {hr} BPM, HRV: {hrv} ms, GSR: {gsr} uS (Status: Success)")
            else:
                print(f"Failed to ingest: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            
        time.sleep(2.0)
        t += 1
except KeyboardInterrupt:
    print("\nMock stream stopped.")
