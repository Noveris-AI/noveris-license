from __future__ import annotations

import base64
import hashlib
import json
from functools import cached_property
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from app.core.config import settings

SUPPORTED_SCHEMA_VERSIONS = {"license.v2"}


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LicenseCrypto:
    def __init__(self):
        self.kid = settings.license_signing_key_id

    @cached_property
    def private_key(self):
        pem = self._load_private_pem()
        return serialization.load_pem_private_key(pem, password=None)

    @cached_property
    def public_key(self):
        pem = self._load_public_pem()
        return serialization.load_pem_public_key(pem)

    def sign_document(self, payload: dict[str, Any], schema_version: str = "license.v2") -> dict[str, Any]:
        signature = self.private_key.sign(
            canonical_json(payload),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {
            "schema_version": schema_version,
            "kid": self.kid,
            "payload": payload,
            "signature": base64.b64encode(signature).decode("utf-8"),
        }

    def verify_document(self, document: dict[str, Any], expected_schema_version: str = "license.v2") -> dict[str, Any]:
        schema_version = document.get("schema_version")
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError("unsupported_schema_version")
        if schema_version != expected_schema_version:
            raise ValueError("unexpected_schema_version")

        if document.get("kid") not in {None, self.kid}:
            raise ValueError("unknown_kid")

        payload = document["payload"]
        signature_raw = base64.b64decode(document["signature"])
        try:
            self.public_key.verify(
                signature_raw,
                canonical_json(payload),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:
            raise ValueError("invalid_signature") from exc
        return payload

    def verify_proof(self, public_key_pem: str, payload: dict[str, Any], signature_b64: str) -> None:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(signature_b64)
        message = canonical_json(payload)
        try:
            if isinstance(public_key, rsa.RSAPublicKey):
                public_key.verify(
                    signature,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            elif isinstance(public_key, ed25519.Ed25519PublicKey):
                public_key.verify(signature, message)
            else:
                raise ValueError("unsupported_public_key_type")
        except InvalidSignature as exc:
            raise ValueError("invalid_proof") from exc

    def public_key_fingerprint(self, public_key_pem: str) -> str:
        return sha256_text(public_key_pem.strip())

    def _load_private_pem(self) -> bytes:
        if settings.license_private_key_pem:
            return settings.license_private_key_pem.encode("utf-8")
        with open(settings.license_private_key_path, "rb") as file_obj:
            return file_obj.read()

    def _load_public_pem(self) -> bytes:
        if settings.license_public_key_pem:
            return settings.license_public_key_pem.encode("utf-8")
        with open(settings.license_public_key_path, "rb") as file_obj:
            return file_obj.read()
