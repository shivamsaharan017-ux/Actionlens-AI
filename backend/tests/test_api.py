import atexit
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

# Isolate each test run from a developer's local database and upload folder.
_test_root = Path(tempfile.mkdtemp(prefix="actionlens-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_test_root / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_test_root / "uploads")
atexit.register(shutil.rmtree, _test_root, ignore_errors=True)

from fastapi.testclient import TestClient
from app.main import app


def test_health_reports_demo_mode_without_provider():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_local_vite_origin_can_call_the_api():
    with TestClient(app) as client:
        response = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_demo_login_and_stats_are_authenticated():
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"email": "demo@actionlens.ai", "password": "ActionLens2026!"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        stats = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
        assert stats.status_code == 200
        assert "total_notices" in stats.json()


def test_admin_stats_rejects_regular_users():
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"email": "demo@actionlens.ai", "password": "ActionLens2026!"})
        token = response.json()["access_token"]
        assert client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_demo_analysis_returns_validated_source_bound_fields():
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"email": "demo@actionlens.ai", "password": "ActionLens2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        result = client.post("/api/notices/analyze", headers=headers, json={"text": "DEMO student grant notice\nThe application must be submitted by 30 October 2026. Attach proof of enrollment. Contact grants@example.edu."})
        assert result.status_code == 200
        payload = result.json()
        assert payload["mode"] == "demo"
        assert payload["analysis"]["deadline"] == "30 October 2026"
        assert payload["analysis"]["required_documents"]
        assert payload["analysis"]["uncertain_information"]


def test_users_cannot_read_each_others_notices():
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"email": "demo@actionlens.ai", "password": "ActionLens2026!"})
        owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        created = client.post("/api/notices/analyze", headers=owner, json={"text": "Private synthetic notice. Please contact help@example.edu."})
        notice_id = created.json()["notice"]["id"]
        email = f"second-{uuid4().hex[:8]}@example.com"
        registered = client.post("/api/auth/register", json={"name": "Second User", "email": email, "password": "secure-pass-123"})
        assert registered.status_code == 200
        stranger = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        assert client.get(f"/api/notices/{notice_id}", headers=stranger).status_code == 404
