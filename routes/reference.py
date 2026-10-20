"""Reference data for form dropdowns, scoped to the caller's organization."""
from datetime import date

from flask import Blueprint, jsonify, request

from auth import role_required
from models import db, ForestPlot, Organization, Permit, Vehicle
from permissions import get_current_user, is_admin

reference_bp = Blueprint('reference', __name__)


@reference_bp.route('/organizations', methods=['GET'])
@role_required('admin')
def list_organizations():
    rows = Organization.query.order_by(Organization.name.asc()).all()
    return jsonify([{
        'id': r.id,
        'name': r.name,
        'type': r.type,
        'registration_number': r.registration_number,
    } for r in rows])


@reference_bp.route('/organizations/<int:organization_id>', methods=['GET'])
@role_required('admin')
def get_organization(organization_id):
    row = db.session.get(Organization, organization_id)
    if not row:
        return jsonify({'error': 'Organization not found'}), 404
    return jsonify({
        'id': row.id,
        'name': row.name,
        'type': row.type,
        'registration_number': row.registration_number,
        'contact': row.contact,
    })


@reference_bp.route('/forest-plots', methods=['GET'])
@role_required('admin', 'forestry_officer')
def list_forest_plots():
    user = get_current_user()
    query = ForestPlot.query

    if not is_admin(user):
        query = query.filter(ForestPlot.org_id == user.org_id)

    rows = query.order_by(ForestPlot.forest_name.asc()).all()
    return jsonify([{
        'id': r.id,
        'name': r.forest_name,
        'org_id': r.org_id,
        'location_lat': r.location_lat,
        'location_lon': r.location_lon,
        'approved_capacity_hectares': r.approved_capacity_hectares,
    } for r in rows])


@reference_bp.route('/permits', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter')
def list_permits():
    user = get_current_user()
    query = Permit.query.filter(
        Permit.status == 'active',
        Permit.expiry_date >= date.today(),
    )

    permit_type = request.args.get('type')
    if permit_type:
        query = query.filter(Permit.type == permit_type)

    if not is_admin(user):
        query = query.filter(Permit.org_id == user.org_id)

    rows = query.order_by(Permit.expiry_date.asc()).all()
    return jsonify([{
        'id': r.id,
        'permit_number': r.permit_number,
        'type': r.type,
        'org_id': r.org_id,
        'issue_date': r.issue_date.isoformat() if r.issue_date else None,
        'expiry_date': r.expiry_date.isoformat() if r.expiry_date else None,
        'status': r.status,
    } for r in rows])


@reference_bp.route('/vehicles', methods=['GET'])
@role_required('admin', 'transporter')
def list_vehicles():
    user = get_current_user()
    query = Vehicle.query

    if not is_admin(user):
        query = query.filter(Vehicle.owner_org_id == user.org_id)

    rows = query.order_by(Vehicle.plate_number.asc()).all()
    return jsonify([{
        'id': r.id,
        'plate_number': r.plate_number,
        'owner_org_id': r.owner_org_id,
        'capacity_m3': r.capacity_m3,
        'current_location': r.current_location,
    } for r in rows])


@reference_bp.route('/recipient-organizations', methods=['GET'])
@role_required('admin', 'transporter', 'mill')
def list_recipient_organizations():
    user = get_current_user()
    requested_type = request.args.get('type', '').lower()
    allowed_type = {
        'transporter': 'mill',
        'mill': 'buyer',
    }.get((user.role or '').lower())

    if not is_admin(user) and requested_type != allowed_type:
        return jsonify({'error': 'You are not authorized to list this recipient type'}), 403
    if requested_type not in {'mill', 'buyer'}:
        return jsonify({'error': 'A supported recipient type is required'}), 400

    rows = Organization.query.filter_by(type=requested_type).order_by(Organization.name.asc()).all()
    return jsonify([{
        'id': row.id,
        'name': row.name,
        'type': row.type,
    } for row in rows])
