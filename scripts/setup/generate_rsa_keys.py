#!/usr/bin/env python3
"""Generate RSA key pair for License signing."""

import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keys(private_path: str = "private.pem", public_path: str = "public.pem"):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    os.makedirs(os.path.dirname(private_path) or ".", exist_ok=True)

    with open(private_path, "wb") as f:
        f.write(private_pem)
    print(f"Private key written to: {private_path}")

    with open(public_path, "wb") as f:
        f.write(public_pem)
    print(f"Public key written to: {public_path}")


if __name__ == "__main__":
    private_path = sys.argv[1] if len(sys.argv) > 1 else "keys/private.pem"
    public_path = sys.argv[2] if len(sys.argv) > 2 else "keys/public.pem"
    generate_keys(private_path, public_path)
