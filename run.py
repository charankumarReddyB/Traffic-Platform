"""Top-level runner for AI-Powered Urban Traffic, Public Transport & Emergency Platform.
Team 10 Capstone Project.

Usage:
    python run.py [--host 127.0.0.1] [--port 8000] [--reload]
"""
import os, sys, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# Ensure backend directory is in sys.path
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("FRONTEND_DIR", str(FRONTEND_DIR))

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Run Urban Traffic Platform")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    args = parser.parse_args()

    print("=" * 70)
    print("AI-Powered Urban Traffic, Public Transport & Emergency Platform")
    print(f"Server URL: http://{args.host}:{args.port}")
    print(f"Backend:    {BACKEND_DIR}")
    print(f"Frontend:   {FRONTEND_DIR}")
    print("=" * 70)

    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload, app_dir=str(BACKEND_DIR))
