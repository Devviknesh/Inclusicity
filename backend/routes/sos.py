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

    return jsonify({
        "message": "SOS alert sent successfully",
        "sos_id": sos_id
    }), 201
