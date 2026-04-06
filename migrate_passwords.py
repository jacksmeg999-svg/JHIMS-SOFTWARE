"""
One-time migration script: hashes all plaintext passwords in the users table.
Run this ONCE in the same folder as your app.py and hospital_web.db.

Usage:
    python migrate_passwords.py
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "hospital_web.db")

def is_already_hashed(password):
    """Werkzeug hashes start with 'pbkdf2:' or 'scrypt:' etc."""
    return password.startswith("pbkdf2:") or password.startswith("scrypt:") or password.startswith("$")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT id, username, password FROM users")
    users = c.fetchall()

    updated = 0
    skipped = 0

    for user in users:
        if is_already_hashed(user["password"]):
            print(f"  [SKIP] {user['username']} — already hashed")
            skipped += 1
        else:
            hashed = generate_password_hash(user["password"])
            c.execute("UPDATE users SET password=? WHERE id=?", (hashed, user["id"]))
            print(f"  [OK]   {user['username']} — password hashed")
            updated += 1

    conn.commit()
    conn.close()

    print(f"\nDone. {updated} password(s) hashed, {skipped} skipped.")

if __name__ == "__main__":
    migrate()
