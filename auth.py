import bcrypt, jwt, functools
from flask import request, jsonify
from datetime import datetime, timedelta
from config import Config
from models import db, User, AuditLog


def role_required(*allowed_roles):
    """Decorator for endpoint-level role checks after JWT middleware."""
    allowed = {r.lower() for r in allowed_roles}

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            payload = getattr(request, 'user', None)
            if not payload:
                return jsonify({'error': 'missing token'}), 401

            role = (payload.get('role') or '').lower()
            if role not in allowed:
                return jsonify({'error': 'forbidden: insufficient privileges'}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _is_authorized(role, endpoint, method):
    """Endpoint-level RBAC for API routes."""
    role = (role or '').lower()

    # Admin keeps full access across authenticated API routes.
    if role == 'admin':
        return True

    # Logger: create batches, and allow batch asset reads.
    if role == 'logger':
        return endpoint in {
            'batches.create_batch',
            'batches.list_batches',
            'batches.get_batch_by_tag',
            'batches.verify_batch',
            'batches.get_qr_code',
            'batches.get_qr_code_data',
            'batches.download_qr_code',
            'users.get_current_user',
        }

    # Transporter: track and update via transactions.
    if role == 'transporter':
        return endpoint in {
            'batches.list_batches',
            'batches.get_batch_by_tag',
            'batches.verify_batch',
            'transactions.list_transactions',
            'transactions.get_transaction',
            'transactions.create_transaction',
            'batches.get_qr_code',
            'batches.get_qr_code_data',
            'batches.download_qr_code',
            'users.get_current_user',
        }

    # Mill: transporter capabilities + blockchain read visibility.
    if role == 'mill':
        return endpoint in {
            'batches.list_batches',
            'batches.get_batch_by_tag',
            'batches.verify_batch',
            'transactions.list_transactions',
            'transactions.get_transaction',
            'transactions.create_transaction',
            'batches.get_qr_code',
            'batches.get_qr_code_data',
            'batches.download_qr_code',
            'blockchain.get_latest_block',
            'blockchain.get_block',
            'blockchain.get_chain',
            'blockchain.verify_chain',
            'users.get_current_user',
        }

    # Inspector and buyer: blockchain viewing only (GET endpoints).
    if role in {'inspector', 'buyer'}:
        return endpoint in {
            'batches.get_batch_by_tag',
            'batches.verify_batch',
            'batches.get_qr_code',
            'batches.get_qr_code_data',
            'batches.download_qr_code',
            'transactions.list_transactions',
            'transactions.get_transaction',
            'blockchain.get_latest_block',
            'blockchain.get_block',
            'blockchain.get_chain',
            'blockchain.verify_chain',
            'users.get_current_user',
        } and method == 'GET'

    return False

def hash_password(pwd): 
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt(rounds=12)).decode()

def check_password(pwd, hash_): 
    return bcrypt.checkpw(pwd.encode(), hash_.encode())

def init_auth(app):
    @app.before_request
    def require_auth():
        # Protect API routes only. Template pages can load, while API data stays secured.
        if not request.path.startswith('/api'):
            return

        # Public API endpoints (no token required)
        public_api_endpoints = {
            'users.login',
        }
        if request.endpoint in public_api_endpoints:
            return

        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Bearer '):
            return jsonify({'error':'missing token'}), 401
        token = auth.split(' ',1)[1]
        try:
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
            request.user = payload
        except: 
            return jsonify({'error':'invalid token'}), 401

        if not _is_authorized(payload.get('role'), request.endpoint, request.method):
            return jsonify({'error': 'forbidden: insufficient privileges'}), 403

def issue_jwt(user_id, role):
    exp = datetime.utcnow() + timedelta(minutes=30)
    return jwt.encode({'user_id':user_id,'role':role,'exp':exp}, Config.SECRET_KEY, algorithm='HS256')

def log_audit(user_id, action, table_affected, record_id, ip):
    try:
        entry = AuditLog(user_id=user_id, action=action, table_affected=table_affected, record_id=record_id, ip_address=ip)
        db.session.add(entry)
        db.session.commit()
    except:
        db.session.rollback()