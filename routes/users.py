from flask import Blueprint, request, jsonify
from models import db, User
from auth import hash_password, check_password, issue_jwt, log_audit, role_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/register', methods=['POST'])
@role_required('admin')
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error':'email exists'}), 400
    u = User(
      name=data['name'], 
      email=data['email'],
      password_hash=hash_password(data['password']),
      role=data['role'], 
      phone=data.get('phone'), 
      org_id=data.get('org_id')
    )
    db.session.add(u)
    db.session.commit()
    log_audit(u.id, 'register', 'users', u.id, request.remote_addr)  # ✅ fixed name
    return jsonify({'message':'created'}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    u = User.query.filter_by(email=data['email']).first()
    if not u or not check_password(data['password'], u.password_hash):
        return jsonify({'error':'invalid credentials'}), 401
    token = issue_jwt(u.id, u.role)
    return jsonify({'token': token, 'role': u.role, 'user_id': u.id})


@users_bp.route('/users', methods=['GET'])
@role_required('admin')
def list_users():
    rows = User.query.all()
    return jsonify([{
      'id': r.id, 'name': r.name, 'email': r.email, 'role': r.role, 'phone': r.phone
    } for r in rows])


@users_bp.route('/me', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill', 'inspector', 'buyer')
def get_current_user():
        return jsonify({
                'user_id': request.user.get('user_id'),
                'role': request.user.get('role')
        })