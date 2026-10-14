# Build-time self-check (Dockerfile smoke step): python test_app.py
# Covers CO2 formatting and the host gate that keeps per-person spend off
# the public host. Needs no database.
import os

os.environ["DASHBOARD_HOST"] = "costs.example.org"
os.environ.pop("LITELLM_DB_URL", None)
os.environ.pop("OPENWEBUI_DB_URL", None)

from fastapi.testclient import TestClient
from main import app, format_co2

# format_co2: input in kg
assert format_co2(0.012) == "12 g", format_co2(0.012)
assert format_co2(0) == "0 g"
assert format_co2(0.00004) == "< 0.1 g"
assert format_co2(0.0004) == "0.4 g"
assert format_co2(0.0054, ",") == "5,4 g"
assert format_co2(0.5) == "500 g"
assert format_co2(0.9996) == "1.00 kg"
assert format_co2(2.7138, ",") == "2,71 kg"

c = TestClient(app)
pub = {"host": "carbon.example.org"}
dash = {"host": "costs.example.org:443"}

# Per-person data never on the public host.
assert c.get("/api/users/costs", headers=pub).status_code == 404
assert c.get("/static/index.html", headers=pub).status_code == 404
r = c.get("/", headers=pub, follow_redirects=False)
assert r.status_code in (302, 307) and r.headers["location"] == "/carbon", r.status_code

# On the dashboard host the gate opens (no DB configured here -> 500, not 404).
assert c.get("/api/users/costs", headers=dash).status_code == 500
assert c.get("/", headers=dash).status_code == 200

# Public page renders on any host, with and without amount.
assert c.get("/carbon", headers=pub).status_code == 200
assert "0.4 g" in c.get("/carbon?amount=0.0004", headers=pub).text
assert c.get("/health", headers=pub).status_code == 200
print("cost-tracker self-check OK")
