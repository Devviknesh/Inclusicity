"""
InclusiCity - Synthetic Demonstration Data & Production Index Seeder
Populates MongoDB Atlas with production indexes and synthetic demonstration accounts.
Zero real user or personal information is used.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/inclusicity")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPass@2026")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@inclusicity.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "AdminPass@2026")


def setup_database_indexes(db):
    print("📦 Configuring production database indexes...")

    # Users
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.users.create_index([("role", ASCENDING)])

    # Helpers
    db.helpers.create_index([("email", ASCENDING)], unique=True)
    db.helpers.create_index([("city", ASCENDING), ("available", ASCENDING)])
    db.helpers.create_index([("verification_status", ASCENDING)])
    db.helpers.create_index([("verified", ASCENDING)])

    # Profiles
    db.profiles.create_index([("user_id", ASCENDING)], unique=True)

    # Requests
    db.requests.create_index([("user_id", ASCENDING)])
    db.requests.create_index([("helper_id", ASCENDING)])
    db.requests.create_index([("city", ASCENDING), ("status", ASCENDING)])
    db.requests.create_index([("needed_at", ASCENDING)])

    # Ratings
    db.ratings.create_index([("request_id", ASCENDING)], unique=True)
    db.ratings.create_index([("helper_id", ASCENDING)])

    # SOS Alerts
    db.sos_alerts.create_index([("status", ASCENDING), ("created_at", DESCENDING)])

    print("✅ Indexes created successfully.")


def seed_synthetic_data(db):
    print("🌱 Seeding synthetic demonstration accounts...")

    hashed_demo_pw = generate_password_hash(DEMO_PASSWORD)
    hashed_admin_pw = generate_password_hash(ADMIN_PASSWORD)

    # 1. Admin Account
    admin = db.users.find_one({"email": ADMIN_EMAIL})
    if not admin:
        admin_id = db.users.insert_one({
            "name": "System Administrator",
            "email": ADMIN_EMAIL,
            "password": hashed_admin_pw,
            "role": "admin",
            "age": 32,
            "city": "Chennai",
            "created_at": datetime.utcnow()
        }).inserted_id
        print(f"  + Admin created: {ADMIN_EMAIL}")
    else:
        admin_id = admin["_id"]
        print(f"  - Admin already exists: {ADMIN_EMAIL}")

    # 2. Demo Normal Users
    demo_users = [
        {
            "name": "Priya Sharma (Demo User)",
            "email": "demo.user@inclusicity.com",
            "password": hashed_demo_pw,
            "age": 29,
            "city": "Chennai",
            "phone": "+91 98765 00001",
            "mobility_needs": "Wheelchair accessible paths and ramps",
            "role": "user",
            "created_at": datetime.utcnow()
        },
        {
            "name": "Ramanathan K. (Demo Senior)",
            "email": "demo.senior@inclusicity.com",
            "password": hashed_demo_pw,
            "age": 68,
            "city": "Chennai",
            "phone": "+91 98765 00002",
            "mobility_needs": "Assistance entering public buildings & visual guiding",
            "role": "user",
            "created_at": datetime.utcnow()
        }
    ]

    user_ids = []
    for u in demo_users:
        existing = db.users.find_one({"email": u["email"]})
        if not existing:
            uid = db.users.insert_one(u).inserted_id
            user_ids.append(uid)
            print(f"  + User created: {u['email']}")
        else:
            user_ids.append(existing["_id"])
            print(f"  - User exists: {u['email']}")

    # 3. Demo Helpers
    demo_helpers = [
        {
            "name": "Karthik Raja (Verified Helper)",
            "email": "demo.helper.verified@inclusicity.com",
            "password": hashed_demo_pw,
            "age": 26,
            "city": "Chennai",
            "phone": "+91 98765 00003",
            "skills": ["Wheelchair Handling", "Navigation Assistance", "First Aid"],
            "verification_status": "verified",
            "profile_completed": True,
            "verified": True,
            "available": True,
            "role": "helper",
            "ngo_id": "ngo_chennai_central",
            "avg_rating": 4.9,
            "total_reviews": 12,
            "documents": {
                "government_ids": {
                    "driving_license": {
                        "file_url": "helpers/demo/sample_license.pdf",
                        "verified": True
                    }
                }
            },
            "created_at": datetime.utcnow() - timedelta(days=30),
            "updated_at": datetime.utcnow()
        },
        {
            "name": "Ananya Iyer (Pending Helper)",
            "email": "demo.helper.pending@inclusicity.com",
            "password": hashed_demo_pw,
            "age": 24,
            "city": "Chennai",
            "phone": "+91 98765 00004",
            "skills": ["Visual Guidance", "Elderly Care", "Sign Language Basics"],
            "verification_status": "submitted",
            "profile_completed": True,
            "verified": False,
            "available": False,
            "role": "helper",
            "ngo_id": "ngo_chennai_south",
            "avg_rating": None,
            "total_reviews": 0,
            "documents": {
                "government_ids": {
                    "aadhaar": {
                        "file_url": "helpers/demo/sample_aadhaar.pdf",
                        "verified": False
                    }
                },
                "address_proof": {
                    "type": "utility_bill",
                    "file_url": "helpers/demo/sample_utility.pdf",
                    "verified": False
                }
            },
            "verification_submitted_at": datetime.utcnow() - timedelta(hours=2),
            "created_at": datetime.utcnow() - timedelta(days=2),
            "updated_at": datetime.utcnow()
        }
    ]

    helper_ids = []
    for h in demo_helpers:
        existing = db.helpers.find_one({"email": h["email"]})
        if not existing:
            hid = db.helpers.insert_one(h).inserted_id
            helper_ids.append(hid)
            print(f"  + Helper created: {h['email']}")
        else:
            helper_ids.append(existing["_id"])
            print(f"  - Helper exists: {h['email']}")

    # 4. Demo Completed Request & Rating
    if user_ids and helper_ids:
        existing_req = db.requests.find_one({"need": "Assistance entering Apollo Hospital lobby"})
        if not existing_req:
            req_id = db.requests.insert_one({
                "user_id": user_ids[0],
                "helper_id": helper_ids[0],
                "city": "Chennai",
                "pickup_address": "Greams Road Gate 1",
                "destination_address": "Apollo Hospitals OPD Floor 2",
                "need": "Assistance entering Apollo Hospital lobby",
                "phone": "+91 98765 00001",
                "needed_date": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
                "needed_time": "10:00",
                "needed_at": datetime.utcnow() - timedelta(days=1),
                "status": "completed",
                "created_at": datetime.utcnow() - timedelta(days=1, hours=2),
                "accepted_at": datetime.utcnow() - timedelta(days=1, hours=1),
                "completed_at": datetime.utcnow() - timedelta(days=1)
            }).inserted_id

            db.ratings.insert_one({
                "request_id": req_id,
                "user_id": user_ids[0],
                "helper_id": helper_ids[0],
                "rating": 5,
                "feedback": "Karthik was punctual, courteous, and extremely helpful during my OPD visit.",
                "created_at": datetime.utcnow() - timedelta(days=1)
            })
            print("  + Demo completed request & 5-star review created.")

    # 5. Demo SOS Record
    existing_sos = db.sos_alerts.find_one({"message": "Demonstration SOS alert: Elevator breakdown at Guindy Metro"})
    if not existing_sos and user_ids:
        db.sos_alerts.insert_one({
            "user_id": str(user_ids[0]),
            "email": "demo.user@inclusicity.com",
            "role": "user",
            "message": "Demonstration SOS alert: Elevator breakdown at Guindy Metro",
            "status": "resolved",
            "created_at": datetime.utcnow() - timedelta(days=3),
            "resolved_at": datetime.utcnow() - timedelta(days=3, minutes=15)
        })
        print("  + Demo resolved SOS alert created.")

    print("\n" + "=" * 60)
    print("DEMO CREDENTIALS SUMMARY (SYNTHETIC ACCOUNTS):")
    print(f"  Admin:            {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Verified Helper:  demo.helper.verified@inclusicity.com / {DEMO_PASSWORD}")
    print(f"  Pending Helper:   demo.helper.pending@inclusicity.com / {DEMO_PASSWORD}")
    print(f"  Demo User:        demo.user@inclusicity.com / {DEMO_PASSWORD}")
    print("=" * 60)


def main():
    print(f"Connecting to MongoDB: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI}")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        sys.exit(1)

    try:
        db = client.get_default_database()
    except Exception:
        db = client["inclusicity"]

    setup_database_indexes(db)
    seed_synthetic_data(db)
    print("\n✅ Setup and synthetic demonstration data complete!")


if __name__ == "__main__":
    main()
