import secrets
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from app.core.license_crypto import canonical_json
from app.core.security import hash_password
from app.modules.issue.models import Operator


def make_install_keypair() -> tuple[str, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return public_pem, private_key


def sign_proof(private_key, payload: dict[str, str]) -> str:
    import base64

    signature = private_key.sign(
        canonical_json(payload),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def seed_operator(db):
    operator = Operator(
        email="test@naviam.local",
        username="Test",
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


class TestAuth:
    def test_login_success(self, client: TestClient, db):
        seed_operator(db)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@naviam.local", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@naviam.local"
        assert "naviam_session" in response.cookies

    def test_login_wrong_password(self, client: TestClient, db):
        seed_operator(db)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@naviam.local", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_logout(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)

        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200


class TestLicenseIssue:
    def test_issue_license(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)

        response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Test Customer",
                "max_nodes": 10,
                "max_gpus": 4,
                "features": {"feature_a": True},
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["license_key"].startswith("NVM-")
        assert data["certificate"]["payload"]["document_type"] == "license"
        assert data["certificate"]["payload"]["features"] == {"feature_a": True}
        assert data["certificate"]["kid"]

    def test_issue_unauthorized(self, client: TestClient):
        response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Test Customer",
                "max_nodes": 10,
                "max_gpus": 4,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            },
        )
        assert response.status_code == 401

    def test_activate_and_renew_online(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)
        issue_response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Online Customer",
                "max_nodes": 3,
                "max_gpus": 1,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            },
        )
        certificate = issue_response.json()["certificate"]
        public_pem, private_key = make_install_keypair()

        activate_response = client.post(
            "/api/v1/licenses/activate",
            json={
                "license_certificate": certificate,
                "cluster_id": "cluster-a",
                "fingerprint": "fingerprint-a",
                "machine_name": "worker-1",
                "install_public_key": public_pem,
            },
        )
        assert activate_response.status_code == 200
        activated = activate_response.json()
        assert activated["activation_certificate"]["payload"]["document_type"] == "activation"
        assert activated["lease"]["payload"]["document_type"] == "lease"
        assert activated["lease"]["payload"]["mode"] == "online"

        request_id = "renew-online-0001"
        client_time = datetime.now(timezone.utc)
        proof_payload = {
            "purpose": "lease_renewal",
            "activation_id": activated["activation_id"],
            "license_key": activated["license_key"],
            "request_id": request_id,
            "client_time": client_time.isoformat(),
            "mode": "online",
        }
        renew_response = client.post(
            "/api/v1/licenses/renew",
            json={
                "activation_id": activated["activation_id"],
                "license_key": activated["license_key"],
                "request_id": request_id,
                "client_time": client_time.isoformat(),
                "proof": sign_proof(private_key, proof_payload),
            },
        )
        assert renew_response.status_code == 200
        renewed = renew_response.json()
        assert renewed["lease"]["payload"]["mode"] == "online"
        assert renewed["lease"]["payload"]["activation_id"] == activated["activation_id"]

    def test_second_activation_is_blocked_when_max_activations_is_one(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)
        issue_response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Strict Customer",
                "max_nodes": 2,
                "max_gpus": 0,
                "max_activations": 1,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            },
        )
        certificate = issue_response.json()["certificate"]
        public_pem_1, _ = make_install_keypair()
        public_pem_2, _ = make_install_keypair()

        first = client.post(
            "/api/v1/licenses/activate",
            json={
                "license_certificate": certificate,
                "cluster_id": "cluster-a",
                "fingerprint": "fingerprint-a",
                "machine_name": "worker-a",
                "install_public_key": public_pem_1,
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/licenses/activate",
            json={
                "license_certificate": certificate,
                "cluster_id": "cluster-b",
                "fingerprint": "fingerprint-b",
                "machine_name": "worker-b",
                "install_public_key": public_pem_2,
            },
        )
        assert second.status_code == 409

    def test_offline_activate_requires_operator_session(self, client: TestClient, db):
        seed_operator(db)
        login_operator(client)
        issue_response = client.post(
            "/api/v1/license/issue",
            json={
                "customer_name": "Offline Customer",
                "max_nodes": 5,
                "max_gpus": 2,
                "activation_mode": "hybrid",
                "offline_lease_ttl_days": 45,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            },
        )
        issued = issue_response.json()
        public_pem, private_key = make_install_keypair()
        request_nonce = secrets.token_hex(32)
        request_time = datetime.now(timezone.utc)
        request_bundle = {
            "license_key": issued["license_key"],
            "cluster_id": "cluster-offline",
            "fingerprint": "offline-fingerprint",
            "machine_name": "offline-node",
            "install_public_key": public_pem,
            "request_nonce": request_nonce,
            "request_time": request_time.isoformat(),
            "client_signature": "",
        }
        proof_payload = {
            "purpose": "offline_activation_request",
            "license_key": request_bundle["license_key"],
            "fingerprint": request_bundle["fingerprint"],
            "cluster_id": request_bundle["cluster_id"],
            "machine_name": request_bundle["machine_name"],
            "install_public_key": request_bundle["install_public_key"],
            "request_nonce": request_bundle["request_nonce"],
            "request_time": request_bundle["request_time"],
        }
        request_bundle["client_signature"] = sign_proof(private_key, proof_payload)

        client.post("/api/v1/auth/logout")
        unauthenticated = client.post(
            "/api/v1/licenses/offline/process-activation",
            json={"request_bundle": request_bundle},
        )
        assert unauthenticated.status_code == 401

        login_operator(client)
        authenticated = client.post(
            "/api/v1/licenses/offline/process-activation",
            json={"request_bundle": request_bundle},
        )
        assert authenticated.status_code == 200
        assert authenticated.json()["lease"]["payload"]["mode"] == "offline"
