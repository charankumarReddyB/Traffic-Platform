import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["RATE_LOGIN_PER_MIN"] = "100000"
os.environ["RATE_API_PER_MIN"] = "100000"
os.environ["ADMIN_EMAIL"] = "boss@x.com"
os.environ["ADMIN_PASSWORD"] = "adminpass1"
# The 6x6 grid is retained as a test fixture for the existing test suite:
os.environ.setdefault("NETWORK_FILE", "__grid_test_fixture__")
