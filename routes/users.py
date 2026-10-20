from flask import Blueprint, request, jsonify
from models import db, User, Organization
from auth import hash_password, check_password, issue_jwt, log_audit, role_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/register', methods=['POST'])
@role_required('admin')
def register():
    data = request.get_json(silent=True) or {}
    missing = [field for field in ('name', 'email', 'password') if not data.get(field)]
    if missing:
        return jsonify({'error': 'Missing required fields', 'fields': missing}), 400

    email = str(data['email']).strip().lower()
    role_name = str(data.get('role', 'forestry_officer')).strip().lower()
    allowed_roles = {'admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer'}
    if role_name not in allowed_roles:
        return jsonify({'error': 'Invalid role'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'email exists'}), 400

    organization_id = data.get('org_id')
    if organization_id not in (None, ''):
        try:
            organization_id = int(organization_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid organization ID'}), 400
        if not db.session.get(Organization, organization_id):
            return jsonify({'error': 'Organization not found'}), 404
    else:
        organization_id = None

    u = User(
        name=str(data['name']).strip(),
        email=email,
        password_hash=hash_password(str(data['password'])),
        phone=data.get('phone'),
        org_id=organization_id,
    )
    db.session.add(u)
    u.role = role_name
    db.session.commit()

    log_audit(u.id, 'register', 'users', u.id, request.remote_addr)
    return jsonify({'message': 'created', 'user_id': u.id}), 201

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
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def get_current_user():
    user = db.session.get(User, request.user.get('user_id'))
    if not user:
        return jsonify({'error': 'user not found'}), 404

    org = db.session.get(Organization, user.org_id) if user.org_id else None
    return jsonify({
        'user_id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'org_id': user.org_id,
        'organization': {
            'id': org.id, 'name': org.name, 'type': org.type
        } if org else None,
    })