#!/usr/bin/env python3
"""Create or update an admin user directly in the DB.
Useful for first-time setup or recovering access without running the full app.

Usage:
    python scripts/create_admin.py --username raymond.xu \
        --email raymond.xu@booming.one --password Admin909217
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

# Allow running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ADMIN_PASSWORD", "admin")

from app.config import get_settings  # noqa: E402
from app.db.session import Base, get_engine, SessionLocal  # noqa: E402
from app.db.models import User, Role  # noqa: E402
from app.auth.passwords import hash_password  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--username", required=True, help="login username")
    p.add_argument("--email", default=None, help="email (optional)")
    p.add_argument("--password", required=True, help="initial password (will be bcrypt-hashed)")
    p.add_argument("--role", default="admin", choices=["admin", "user"])
    p.add_argument("--reset", action="store_true", help="if user exists, reset password and re-enable")
    args = p.parse_args()

    get_settings.cache_clear()
    Base.metadata.create_all(get_engine())

    with SessionLocal() as db:
        u = db.query(User).filter_by(username=args.username).first()
        if u is None:
            u = User(
                username=args.username,
                email=args.email,
                password_hash=hash_password(args.password),
                role=Role(args.role),
                is_active=True,
            )
            db.add(u)
            db.commit()
            print(f"created {args.role} user: {args.username} ({u.email or 'no email'})")
        else:
            changed = False
            if args.email and u.email != args.email:
                u.email = args.email
                changed = True
            if args.reset or not u.password_hash:
                u.password_hash = hash_password(args.password)
                changed = True
            if not u.is_active:
                u.is_active = True
                changed = True
            if u.role != Role(args.role):
                u.role = Role(args.role)
                changed = True
            if changed:
                db.commit()
                print(f"updated existing user: {args.username}")
            else:
                print(f"user already exists: {args.username} (use --reset to reset password)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())