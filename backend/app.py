import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, send_from_directory, send_file, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_restx import Api
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

from routes.voice import socketio

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.join(os.path.dirname(BASE_DIR), "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="/")

# -------------------- CORS --------------------
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS.split(",") if "," in ALLOWED_ORIGINS else ALLOWED_ORIGINS}})

# -------------------- JWT --------------------
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "inclusicity-super-secure-jwt-secret-key-change-in-production")
app.config["JWT_ALGORITHM"] = "HS256"
app.config["JWT_EXPIRY_HOURS"] = int(os.getenv("JWT_EXPIRY_HOURS", 24))
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
jwt = JWTManager(app)

# -------------------- EMAIL --------------------
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["FRONTEND_URL"] = os.getenv("FRONTEND_URL", "http://localhost:5173")

# -------------------- MongoDB --------------------
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/inclusicity")
mongo = PyMongo(app)

# -------------------- Secure Document Uploads --------------------
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.route("/uploads/<path:filename>")
def uploaded_files(filename):
    """
    Secure document route: requires JWT token via header or query param.
    Admins can view any helper verification document.
    Helpers can only view their own uploaded verification documents.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.args.get("token"):
        token = request.args.get("token")

    if not token:
        return jsonify({"error": "Authorization token required to access verification documents"}), 401

    try:
        from routes.auth import decode_jwt
        user = decode_jwt(token)
    except Exception as e:
        return jsonify({"error": "Invalid or expired token"}), 401

    role = user.get("role")
    user_id = str(user.get("user_id"))

    # Admin has full review access to verification documents
    if role == "admin":
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # Helper can view only their own documents
    if role == "helper" and filename.startswith(f"helpers/{user_id}/"):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    return jsonify({"error": "Access denied: insufficient permissions for requested document"}), 403

# -------------------- Health & Status --------------------
@app.route("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "inclusicity-backend",
        "timestamp": os.environ.get("BUILD_TIMESTAMP", "live")
    }), 200

@app.route("/api")
def api_root():
    return jsonify({"message": "InclusiCity backend running", "version": "1.0"})

# -------------------- Swagger API --------------------
api = Api(
    app,
    title="InclusiCity API",
    version="1.0",
    description="Role-based accessibility assistance platform backend",
    doc="/docs",
    authorizations={
        "Bearer": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization"
        }
    },
    security="Bearer"
)

# -------------------- Blueprints --------------------
from routes.auth import auth_bp, auth_ns
from routes.requests import requests_bp, requests_ns
from routes.admin import admin_bp, admin_ns
from routes.ratings import ratings_bp, ratings_ns
from routes.sos import sos_bp
from routes.helpers import helpers_bp
from routes.profile import profile_bp

app.register_blueprint(helpers_bp)
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(requests_bp, url_prefix="/requests")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(ratings_bp, url_prefix="/ratings")
app.register_blueprint(sos_bp)
app.register_blueprint(profile_bp, url_prefix="/profile")

api.add_namespace(auth_ns, path="/auth")
api.add_namespace(requests_ns, path="/requests")
api.add_namespace(admin_ns, path="/admin")
api.add_namespace(ratings_ns, path="/ratings")

# -------------------- Serve React Frontend (Single Process Mode) --------------------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    elif os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
        return send_file(os.path.join(FRONTEND_DIST, "index.html"))
    else:
        return jsonify({"message": "InclusiCity API is running. Frontend is deployed independently."}), 200

# -------------------- Socket.IO Init --------------------
socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
