from __future__ import annotations

import argparse

from .database import SessionLocal
from .models import User


def main() -> None:
    parser = argparse.ArgumentParser(description='Grant or revoke full store admin access for an existing user.')
    parser.add_argument('email', help='Email address of a registered account')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--grant', action='store_true')
    action.add_argument('--revoke', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email.lower()).first()
        if user is None:
            parser.error('Registered account not found')
        user.is_admin = args.grant
        db.commit()
        print(f'Store admin access {"granted" if args.grant else "revoked"} for {user.email}')


if __name__ == '__main__':
    main()
