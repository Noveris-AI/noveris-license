from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.issue.models import Operator


def seed_operator(db):
    operator = Operator(
        email="test@naviam.local",
        username="Verifier",
        password_hash=hash_password("password123"),
    )
    db.add(operator)
    db.commit()


def login_operator(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@naviam.local", "password": "password123"},
    )
    assert response.status_code == 200


class TestVerify:
    def test_verify_invalid_format(self, client: TestClient):
        response = client.post(
            "/api/v1/license/verify",
            json={"license_data": {"invalid": "data"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "invalid_signature"

    def test_verify_invalid_signature(self, client: TestClient):
        response = client.post(
            "/api/v1/license/verify",
            json={
                "license_data": {
                    "payload": {"license_key": "NVM-TEST", "document_type": "license"},
                    "signature": "invalid_base64!!!",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["reason"] == "invalid_signature"

    def test_verify_issued_license_and_revoked_license(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)

        issue_response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Verify Customer",
                "max_nodes": 8,
                "max_gpus": 2,
                "cluster_id": "verify-cluster",
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            },
        )
        assert issue_response.status_code == 200
        issued = issue_response.json()

        verify_response = client.post(
            "/api/v1/license/verify",
            json={
                "license_data": issued["certificate"],
                "cluster_id": "verify-cluster",
            },
        )
        assert verify_response.status_code == 200
        verified = verify_response.json()
        assert verified["valid"] is True
        assert verified["document_type"] == "license"

        revoke_response = client.post(
            f"/api/v1/licenses/{issued['license_id']}/revoke",
            json={"reason": "Customer terminated contract"},
        )
        assert revoke_response.status_code == 200

        verify_revoked = client.post(
            "/api/v1/license/verify",
            json={
                "license_data": issued["certificate"],
                "cluster_id": "verify-cluster",
            },
        )
        assert verify_revoked.status_code == 200
        revoked_data = verify_revoked.json()
        assert revoked_data["valid"] is False
        assert revoked_data["reason"] == "revoked"
