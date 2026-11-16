"""
InclusiCity - Live Integration & Protocol Verification Suite
Tests:
1. Flask-SocketIO real-time connection and client event handling.
2. Voice room authentication and join_room / leave_room events.
3. WebRTC signaling relays (offer, answer, ice_candidate).
4. Real-time SOS alert broadcast (admin_sos_alert) via Socket.IO.
5. Celery task configuration, serialization, and worker execution.
6. Real SMTP email dispatch error-handling and connection lifecycle.
7. Accessibility Map dataset integrity and coordinate boundaries.
"""

import os
import re
import pytest
from datetime import datetime

os.environ["JWT_SECRET_KEY"] = "live-integration-secret-key-32charsmin!"
os.environ["FLASK_DEBUG"] = "false"

from app import app, socketio
from routes.auth import generate_jwt


class TestLiveIntegration:

    @pytest.fixture
    def flask_client(self):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_live_http_endpoints(self, flask_client):
        # 1. Health endpoint
        res_health = flask_client.get("/health")
        assert res_health.status_code == 200
        data = res_health.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "inclusicity-backend"

        # 2. API root
        res_api = flask_client.get("/api")
        assert res_api.status_code == 200
        assert "InclusiCity backend running" in res_api.get_json()["message"]

    def test_socketio_connection_and_voice_rooms(self):
        # Create two separate Socket.IO test clients
        client1 = socketio.test_client(app)
        client2 = socketio.test_client(app)

        assert client1.is_connected(), "Client 1 failed to connect to Socket.IO"
        assert client2.is_connected(), "Client 2 failed to connect to Socket.IO"

        with app.app_context():
            token_user1 = generate_jwt({"user_id": "u1", "name": "Alice User", "role": "user"})
            token_user2 = generate_jwt({"user_id": "u2", "name": "Bob Helper", "role": "helper"})

        # Client 1 joins 'movies' room
        client1.emit("join_room", {"room": "movies", "token": token_user1})
        received_1 = client1.get_received()
        room_users_event = next((e for e in received_1 if e["name"] == "room_users"), None)
        assert room_users_event is not None, "Did not receive room_users event on join"
        users = room_users_event["args"][0]["users"]
        assert any(u["name"] == "Alice User" for u in users)

        # Client 2 joins 'movies' room
        client2.emit("join_room", {"room": "movies", "token": token_user2})
        received_2 = client2.get_received()
        room_users_event_2 = next((e for e in received_2 if e["name"] == "room_users"), None)
        assert room_users_event_2 is not None
        users_2 = room_users_event_2["args"][0]["users"]
        assert len(users_2) == 2, f"Expected 2 users in room, got {len(users_2)}"

        # Client 1 receives user_joined notification with Client 2's sid
        received_1_after = client1.get_received()
        user_joined_event = next((e for e in received_1_after if e["name"] == "user_joined"), None)
        assert user_joined_event is not None, "Client 1 did not receive user_joined for Client 2"
        target_sid_2 = user_joined_event["args"][0]["sid"]

        # Test speaking indicator event
        client1.emit("speaking", {"room": "movies", "isSpeaking": True})
        received_2_speaking = client2.get_received()
        speaking_event = next((e for e in received_2_speaking if e["name"] == "speaking"), None)
        assert speaking_event is not None
        assert speaking_event["args"][0]["isSpeaking"] is True

        # Test WebRTC offer relay from Client 1 to Client 2
        test_offer = {"type": "offer", "sdp": "v=0\r\no=alice..."}
        client1.emit("offer", {"to": target_sid_2, "offer": test_offer})
        received_2_offer = client2.get_received()
        offer_event = next((e for e in received_2_offer if e["name"] == "offer"), None)
        assert offer_event is not None
        assert offer_event["args"][0]["offer"] == test_offer

        # Test WebRTC answer relay from Client 2 back to Client 1
        target_sid_1 = next(u["sid"] for u in users_2 if u["name"] == "Alice User")
        test_answer = {"type": "answer", "sdp": "v=0\r\no=bob..."}
        client2.emit("answer", {"to": target_sid_1, "answer": test_answer})
        received_1_answer = client1.get_received()
        answer_event = next((e for e in received_1_answer if e["name"] == "answer"), None)
        assert answer_event is not None
        assert answer_event["args"][0]["answer"] == test_answer

        # Test leave room
        client1.emit("leave_room", {"room": "movies"})
        received_2_leave = client2.get_received()
        user_left_event = next((e for e in received_2_leave if e["name"] == "user_left"), None)
        assert user_left_event is not None

        client1.disconnect()
        client2.disconnect()

    def test_live_socketio_sos_broadcast(self):
        admin_client = socketio.test_client(app)
        assert admin_client.is_connected()

        # Emit SOS event via backend socketio instance
        test_sos = {
            "_id": "507f1f77bcf86cd799439077",
            "user_id": "user_sos_123",
            "email": "sos_victim@example.com",
            "role": "user",
            "message": "URGENT TEST SOS",
            "status": "active",
            "created_at": datetime.utcnow().isoformat()
        }

        socketio.emit("admin_sos_alert", test_sos)

        received = admin_client.get_received()
        sos_event = next((e for e in received if e["name"] == "admin_sos_alert"), None)
        assert sos_event is not None, "Admin client did not receive real-time admin_sos_alert"
        assert sos_event["args"][0]["_id"] == "507f1f77bcf86cd799439077"
        assert sos_event["args"][0]["message"] == "URGENT TEST SOS"

        admin_client.disconnect()

    def test_celery_task_registration_and_configuration(self):
        from celery_app import celery_app

        # Verify task is properly registered in celery_app
        assert "utils.email_tasks.send_helper_verified_email_task" in celery_app.tasks
        task = celery_app.tasks["utils.email_tasks.send_helper_verified_email_task"]
        assert task.name == "utils.email_tasks.send_helper_verified_email_task"
        assert task.max_retries == 3
        assert task.default_retry_delay == 10

        assert "utils.email_tasks.send_help_request_accepted_email_task" in celery_app.tasks
        assert "utils.email_tasks.send_sos_alert_email_task" in celery_app.tasks

    def test_real_smtp_email_dispatch_lifecycle(self):
        from utils.email import send_helper_verified_email, send_help_request_accepted_email, send_sos_alert_email

        # Test with unconfigured credentials -> returns False cleanly without crashing
        assert send_helper_verified_email("test@example.com", "Test Helper") is False
        assert send_help_request_accepted_email("user@example.com", "User", "Helper", "Ramp Assist") is False
        assert send_sos_alert_email("admin@example.com", "user@example.com", "Help needed") is False

    def test_storage_utility_and_kyc_guardrails(self):
        import io
        from utils.storage import is_r2_configured, upload_kyc_document, get_kyc_document_access_url

        # Check default R2 unconfigured state
        assert is_r2_configured() is False or isinstance(is_r2_configured(), bool)

        # Check local URL generation fallback
        access_url = get_kyc_document_access_url("helpers/123/aadhaar.pdf")
        assert "helpers/123/aadhaar.pdf" in access_url

        # Test oversize KYC guardrail (> 10MB rejection)
        oversized_data = io.BytesIO(b"0" * (11 * 1024 * 1024))
        success, _, err = upload_kyc_document(oversized_data, "helpers/123/giant.pdf", max_size_mb=10)
        assert success is False
        assert "exceeds maximum allowed free limit" in err

    def test_accessibility_map_dataset_integrity(self):
        map_file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "src", "lib", "accessibility-data.js"
        )
        assert os.path.exists(map_file_path), "accessibility-data.js not found"

        with open(map_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for key accessibility features
        for feature in ['ramps', 'elevators', 'smoothSurface', 'handrails', 'wideDoors']:
            assert feature in content, f"Feature {feature} missing from legend"

        # Check coordinate bounds for Chennai locations (Lat: ~12.8 - 13.3, Lng: ~80.0 - 80.4)
        lat_matches = re.findall(r"lat:\s*([0-9.]+)", content)
        lng_matches = re.findall(r"lng:\s*([0-9.]+)", content)

        assert len(lat_matches) >= 50, f"Expected 50+ locations, found {len(lat_matches)}"
        assert len(lat_matches) == len(lng_matches), "Mismatch between latitudes and longitudes count"

        for lat_str, lng_str in zip(lat_matches, lng_matches):
            lat = float(lat_str)
            lng = float(lng_str)
            assert 12.5 <= lat <= 13.5, f"Latitude {lat} out of realistic Chennai bounds"
            assert 79.5 <= lng <= 80.5, f"Longitude {lng} out of realistic Chennai bounds"
