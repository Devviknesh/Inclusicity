import os
import io
import jwt
import pytest
import mongomock
from bson import ObjectId
from datetime import datetime

# Set testing environment before app import
os.environ["JWT_SECRET_KEY"] = "test-secret-key-12345678901234567890"
os.environ["MONGO_URI"] = "mongodb://localhost:27017/test_inclusicity"

from app import app
from routes.auth import generate_jwt, decode_jwt


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    db = client["test_inclusicity"]
    return db


@pytest.fixture
def client(mock_db, monkeypatch):
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-secret-key-12345678901234567890"
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_EXPIRY_HOURS"] = 24

    # Patch get_db across all route modules
    import routes.auth
    import routes.requests
    import routes.admin
    import routes.ratings
    import routes.sos
    import routes.helpers
    import routes.profile

    monkeypatch.setattr(routes.auth, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.requests, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.admin, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.ratings, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.sos, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.helpers, "get_db", lambda: mock_db)
    monkeypatch.setattr(routes.profile, "get_db", lambda: mock_db)

    with app.test_client() as test_client:
        yield test_client


def test_health_and_api_root(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "inclusicity-backend"

    res_api = client.get("/api")
    assert res_api.status_code == 200
    assert "InclusiCity backend running" in res_api.get_json()["message"]


def test_user_signup_and_login(client, mock_db):
    signup_payload = {
        "name": "Jane User",
        "email": "jane@example.com",
        "password": "securepassword123",
        "age": 28,
        "city": "Chennai",
        "phone": "+91 9876543210",
        "mobility_needs": "Wheelchair accessible paths required"
    }
    res = client.post("/auth/signup", json=signup_payload)
    assert res.status_code == 201

    # Duplicate registration test
    res_dup = client.post("/auth/signup", json=signup_payload)
    assert res_dup.status_code == 409

    # Login test
    login_res = client.post("/auth/login", json={
        "email": "jane@example.com",
        "password": "securepassword123"
    })
    assert login_res.status_code == 200
    data = login_res.get_json()
    assert "token" in data
    assert data["role"] == "user"

    # Verify JWT decode within app context
    with app.app_context():
        payload = decode_jwt(data["token"])
        assert payload["email"] == "jane@example.com"
        assert payload["role"] == "user"


def test_helper_signup_and_profile_submission(client, mock_db):
    helper_data = {
        "name": "Alex Helper",
        "email": "alex@example.com",
        "password": "helperpassword123",
        "age": "25",
        "city": "Chennai",
        "phone": "+91 9876543211",
        "skills": "First Aid, Wheelchair Handling, Navigation"
    }
    res = client.post("/auth/signup/helper", data=helper_data)
    assert res.status_code == 201

    helper = mock_db.helpers.find_one({"email": "alex@example.com"})
    assert helper is not None
    assert helper["verification_status"] == "draft"
    assert helper["verified"] is False
    assert helper["available"] is False


def test_kyc_document_access_control(client, mock_db):
    helper_id = "507f1f77bcf86cd799439011"
    other_helper_id = "507f1f77bcf86cd799439022"
    doc_dir = os.path.join(app.config["UPLOAD_FOLDER"], "helpers", helper_id, "government_ids")
    os.makedirs(doc_dir, exist_ok=True)
    doc_path = os.path.join(doc_dir, "aadhaar.pdf")
    with open(doc_path, "w") as f:
        f.write("DUMMY_AADHAAR_KYC_CONTENT")

    relative_url = f"helpers/{helper_id}/government_ids/aadhaar.pdf"

    # 1. Unauthenticated access -> 401
    res_no_auth = client.get(f"/uploads/{relative_url}")
    assert res_no_auth.status_code == 401

    # 2. Invalid token -> 401
    res_bad_token = client.get(f"/uploads/{relative_url}?token=invalid.jwt.token")
    assert res_bad_token.status_code == 401

    with app.app_context():
        other_helper_token = generate_jwt({
            "user_id": other_helper_id,
            "email": "other@example.com",
            "role": "helper"
        })
        owner_token = generate_jwt({
            "user_id": helper_id,
            "email": "owner@example.com",
            "role": "helper"
        })
        admin_token = generate_jwt({
            "user_id": "507f1f77bcf86cd799439099",
            "email": "admin@inclusicity.com",
            "role": "admin"
        })

    # 3. Unauthorized helper (different ID) -> 403
    res_wrong_helper = client.get(
        f"/uploads/{relative_url}",
        headers={"Authorization": f"Bearer {other_helper_token}"}
    )
    assert res_wrong_helper.status_code == 403

    # 4. Owning helper -> 200
    res_owner = client.get(
        f"/uploads/{relative_url}",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert res_owner.status_code == 200
    assert b"DUMMY_AADHAAR_KYC_CONTENT" in res_owner.data

    # 5. Admin access via query param -> 200
    res_admin = client.get(f"/uploads/{relative_url}?token={admin_token}")
    assert res_admin.status_code == 200
    assert b"DUMMY_AADHAAR_KYC_CONTENT" in res_admin.data

    try:
        os.remove(doc_path)
    except Exception:
        pass


def test_complete_help_request_and_rating_lifecycle(client, mock_db):
    user_id = ObjectId()
    helper_id = ObjectId()

    mock_db.users.insert_one({
        "_id": user_id,
        "name": "Test Requester",
        "email": "requester@example.com",
        "role": "user"
    })

    mock_db.helpers.insert_one({
        "_id": helper_id,
        "name": "Active Helper",
        "email": "activehelper@example.com",
        "city": "Chennai",
        "role": "helper",
        "verified": True,
        "verification_status": "verified",
        "available": True,
        "avg_rating": None,
        "total_reviews": 0
    })

    with app.app_context():
        user_token = generate_jwt({
            "user_id": str(user_id),
            "email": "requester@example.com",
            "role": "user"
        })
        helper_token = generate_jwt({
            "user_id": str(helper_id),
            "email": "activehelper@example.com",
            "role": "helper"
        })

    # Step 1: User creates help request
    req_payload = {
        "city": "Chennai",
        "pickup_address": "12 Anna Salai",
        "destination_address": "Apollo Hospitals",
        "need": "Assistance entering building and navigating elevator",
        "phone": "+91 9999988888",
        "needed_date": "2026-12-01",
        "needed_time": "14:30"
    }
    create_res = client.post(
        "/requests",
        json=req_payload,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert create_res.status_code == 201
    request_id = create_res.get_json()["request_id"]

    # Step 2: Helper views available requests
    avail_res = client.get(
        "/requests/available",
        headers={"Authorization": f"Bearer {helper_token}"}
    )
    assert avail_res.status_code == 200
    requests_list = avail_res.get_json()["available_requests"]
    assert any(r["request_id"] == request_id for r in requests_list)

    # Step 3: Helper accepts request
    accept_res = client.patch(
        f"/requests/{request_id}/accept",
        headers={"Authorization": f"Bearer {helper_token}"}
    )
    assert accept_res.status_code == 200

    # Verify request status is now accepted and helper availability turned to False
    updated_req = mock_db.requests.find_one({"_id": ObjectId(request_id)})
    assert updated_req["status"] == "accepted"
    updated_helper = mock_db.helpers.find_one({"_id": helper_id})
    assert updated_helper["available"] is False

    # Step 4: Helper completes request
    complete_res = client.patch(
        f"/requests/{request_id}/complete",
        headers={"Authorization": f"Bearer {helper_token}"}
    )
    assert complete_res.status_code == 200

    # Verify request is completed and helper is available again
    completed_req = mock_db.requests.find_one({"_id": ObjectId(request_id)})
    assert completed_req["status"] == "completed"
    reavailable_helper = mock_db.helpers.find_one({"_id": helper_id})
    assert reavailable_helper["available"] is True

    # Step 5: User rates the completed helper
    rating_payload = {
        "request_id": request_id,
        "rating": 5,
        "feedback": "Outstanding assistance! Very patient and punctual."
    }
    rate_res = client.post(
        "/ratings",
        json=rating_payload,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert rate_res.status_code == 201
    assert rate_res.get_json()["avg_rating"] == 5.0

    # Verify helper record updated with rating
    rated_helper = mock_db.helpers.find_one({"_id": helper_id})
    assert rated_helper["avg_rating"] == 5.0
    assert rated_helper["total_reviews"] == 1


def test_sos_alert_creation_and_admin_resolution(client, mock_db):
    user_id = ObjectId()
    admin_id = ObjectId()

    with app.app_context():
        user_token = generate_jwt({
            "user_id": str(user_id),
            "email": "emergency_user@example.com",
            "role": "user"
        })
        admin_token = generate_jwt({
            "user_id": str(admin_id),
            "email": "admin@inclusicity.com",
            "role": "admin"
        })

    # Trigger SOS
    sos_res = client.post(
        "/sos",
        json={"message": "Urgent assistance needed near Central Metro!"},
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert sos_res.status_code == 201
    sos_id = sos_res.get_json()["sos_id"]

    # Verify SOS in DB
    sos_doc = mock_db.sos_alerts.find_one({"_id": ObjectId(sos_id)})
    assert sos_doc["status"] == "active"
    assert sos_doc["message"] == "Urgent assistance needed near Central Metro!"

    # Admin fetches SOS list
    admin_sos_res = client.get(
        "/admin/sos",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_sos_res.status_code == 200
    sos_items = admin_sos_res.get_json()["sos"]
    assert any(str(s["_id"]) == sos_id for s in sos_items)

    # Admin resolves SOS
    resolve_res = client.patch(
        f"/admin/sos/{sos_id}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resolve_res.status_code == 200

    resolved_doc = mock_db.sos_alerts.find_one({"_id": ObjectId(sos_id)})
    assert resolved_doc["status"] == "resolved"
    assert "resolved_at" in resolved_doc


def test_seed_admin_logic(mock_db, monkeypatch):
    import seed_admin
    from werkzeug.security import check_password_hash

    # Patch MongoClient in seed_admin to use mock client
    mock_client = mongomock.MongoClient()
    monkeypatch.setattr(seed_admin, "MongoClient", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr(seed_admin, "ADMIN_EMAIL", "admin@inclusicity.com")
    monkeypatch.setattr(seed_admin, "ADMIN_PASSWORD", "SuperSecureAdminPassword!2026")
    monkeypatch.setattr(seed_admin, "ADMIN_NAME", "Platform Root Admin")

    # Initial seed
    seed_admin.seed_admin(reset=False)

    db = mock_client["inclusicity"]
    admin = db.users.find_one({"email": "admin@inclusicity.com"})
    assert admin is not None
    assert admin["role"] == "admin"
    assert check_password_hash(admin["password"], "SuperSecureAdminPassword!2026")

    # Idempotent re-run without reset
    seed_admin.seed_admin(reset=False)
    assert db.users.count_documents({"email": "admin@inclusicity.com"}) == 1

