# run.py
"""
Developer: Mohibul Hoque (hokworks@gmail.com)
LinkedIn: linkedin.com/in/speedymohibul

Entry point to run the H-SEF real-time processing pipeline and dashboard.
Starts the FastAPI application on http://127.0.0.1:8000
"""

import uvicorn
from h_sef.config import HOST, PORT

if __name__ == "__main__":
    print("==================================================================")
    print("   Starting Hyper-Personalized Sensory Environment Fabric (H-SEF)")
    print("                 Phase 1 Development System")
    print(f"      Dashboard available at: http://{HOST}:{PORT}")
    print("==================================================================")
    
    uvicorn.run("h_sef.app:app", host=HOST, port=PORT, reload=False)
