from routes.auth import jwt_required, get_db
from flask import Blueprint, request, jsonify
from datetime import datetime
from routes.voice import socketio

sos_bp = Blueprint("sos", __name__)

@sos_bp.route("/sos", methods=["POST"])
@jwt_required
def create_sos():
    data = request.get_json() or {}
    user = request.user

    created_at = datetime.utcnow()
    sos_doc = {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "message": data.get("message", "Emergency SOS triggered"),
        "status": "active",
        "created_at": created_at,
    }

    db = get_db()
    result = db.sos_alerts.insert_one(sos_doc)
    sos_id = str(result.inserted_id)

    # Real-time notification to listening admin clients via Socket.IO
    try:
        alert_payload = {
            "_id": sos_id,
            "user_id": user["user_id"],
            "email": user["email"],
            "role": user["role"],
            "message": sos_doc["message"],
            "status": "active",
            "created_at": created_at.isoformat()
        }
        socketio.emit("admin_sos_alert", alert_payload)
    except Exception as e:
        print("⚠️ SocketIO SOS alert emission error:", e)

    # Asynchronous email notification to administrator
    import os
    admin_email = os.getenv("ADMIN_EMAIL")
    if admin_email:
        try:
            from utils.email_tasks import send_sos_alert_email_task
            send_sos_alert_email_task.delay(admin_email, user["email"], sos_doc["message"])
        except Exception:
            try:
                from utils.email import send_sos_alert_email
                send_sos_alert_email(admin_email, user["email"], sos_doc["message"])
            except Exception as e:
                print("⚠️ SOS email notification error:", e)

    return jsonify({
        "message": "SOS alert sent successfully",
        "sos_id": sos_id
    }), 201
