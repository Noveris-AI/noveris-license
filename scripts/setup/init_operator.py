#!/usr/bin/env python3
"""Initialize the first operator account."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "backend", "api"))

from app.core.security import hash_password
from app.modules.issue.models import Operator, SessionLocal


def init_operator(email: str = "admin@naviam.local", username: str = "Admin", password: str = "admin123"):
    db = SessionLocal()
    try:
        existing = db.query(Operator).filter(Operator.email == email).first()
        if existing:
            print(f"Operator {email} already exists.")
            return

        op = Operator(
            email=email,
            username=username,
            password_hash=hash_password(password),
        )
        db.add(op)
        db.commit()
        print(f"Operator created: {email} / {password}")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="admin@naviam.local")
    parser.add_argument("--username", default="Admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    init_operator(args.email, args.username, args.password)
