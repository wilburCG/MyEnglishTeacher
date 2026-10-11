"""把某手机号提升为管理员。

用法（容器内）：python -m scripts.make_admin --phone 13800138000
"""
import argparse

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.phone == args.phone))
        if user is None:
            print(f"user {args.phone} not found; they must log in once first")
            return
        user.role = "admin"
        db.commit()
        print(f"{args.phone} ({user.display_name}) is now admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
