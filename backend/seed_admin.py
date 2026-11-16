"""
InclusiCity - Production Admin Initialization Script
Safely provisions the primary administrator account using environment variables.
"""

import os
import sys
import secrets
import string
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# Load environment configuration
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/inclusicity")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@inclusicity.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_NAME = os.getenv("ADMIN_NAME", "System Administrator").strip()


def generate_secure_password(length=16):
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(characters) for _ in range(length))


def seed_admin(reset=False):
    print(f"Connecting to MongoDB at: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI}")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Verify connection
        client.admin.command("ping")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        sys.exit(1)

    try:
        db = client.get_default_database()
    except Exception:
        db = client["inclusicity"]

    existing_admin = db.users.find_one({"email": ADMIN_EMAIL})

    if existing_admin and not reset:
        print(f"Admin account ({ADMIN_EMAIL}) already exists. No changes made.")
        print("To reset the password, run: python seed_admin.py --reset")
        return

    password = ADMIN_PASSWORD
    generated = False
    if not password:
        password = generate_secure_password()
        generated = True

    hashed_password = generate_password_hash(password)

    admin_doc = {
        "name": ADMIN_NAME,
        "email": ADMIN_EMAIL,
        "password": hashed_password,
        "role": "admin",
        "age": 30,
        "city": "Chennai",
        "updated_at": datetime.utcnow()
    }

    if existing_admin and reset:
        db.users.update_one({"email": ADMIN_EMAIL}, {"$set": admin_doc})
        print(f"Admin password for {ADMIN_EMAIL} successfully reset.")
    else:
        admin_doc["created_at"] = datetime.utcnow()
        db.users.insert_one(admin_doc)
        print(f"Admin account created successfully for: {ADMIN_EMAIL}")

    if generated:
        print("-" * 60)
        print("TEMPORARY ONE-TIME GENERATED PASSWORD:")
        print(password)
        print("Please save this password securely or set ADMIN_PASSWORD in your .env.")
        print("-" * 60)
    else:
        print("Admin password provisioned from environment variable ADMIN_PASSWORD.")


if __name__ == "__main__":
    is_reset = "--reset" in sys.argv
    seed_admin(reset=is_reset)
