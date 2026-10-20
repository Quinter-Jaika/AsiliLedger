"""Object-level authorization checks shared by every route that accepts an ID."""
from datetime import date

from flask import jsonify, request

from models import db, ForestPlot, Permit, TimberBatch, Transaction, User, Vehicle


def get_current_user():
    user_id = (getattr(request, 'user', None) or {}).get('user_id')
    if user_id is None:
        return None
    return db.session.get(User, user_id)


def is_admin(user):
    return bool(user) and (user.role or '').lower() == 'admin'


def can_access_organization(user, org_id):
    if is_admin(user):
        return True
    return bool(user) and org_id is not None and user.org_id == org_id


def can_access_plot(user, plot_id):
    plot = db.session.get(ForestPlot, plot_id)

    if not plot:
        return None, (jsonify({'error': 'Forest plot not found'}), 404)

    if not can_access_organization(user, plot.org_id):
        return None, (jsonify({'error': 'You are not authorized to use this forest plot'}), 403)

    return plot, None


def can_access_permit(user, permit_id, required_type=None):
    permit = db.session.get(Permit, permit_id)

    if not permit:
        return None, (jsonify({'error': 'Permit not found'}), 404)

    if not can_access_organization(user, permit.org_id):
        return None, (jsonify({'error': 'You are not authorized to use this permit'}), 403)

    if permit.status != 'active':
        return None, (jsonify({'error': 'Selected permit is not active'}), 400)

    if permit.expiry_date and permit.expiry_date < date.today():
        return None, (jsonify({'error': 'The selected permit has expired'}), 400)

    if required_type and permit.type != required_type:
        return None, (jsonify({'error': f'Selected permit is not a {required_type} permit'}), 400)

    return permit, None


def can_access_vehicle(user, vehicle_id):
    vehicle = db.session.get(Vehicle, vehicle_id)

    if not vehicle:
        return None, (jsonify({'error': 'Vehicle not found'}), 404)

    if not can_access_organization(user, vehicle.owner_org_id):
        return None, (jsonify({'error': 'You are not authorized to use this vehicle'}), 403)

    return vehicle, None


def can_access_batch(user, batch_id, allow_unassigned_load=False):
    batch = db.session.get(TimberBatch, batch_id)

    if not batch:
        return None, (jsonify({'error': 'Timber batch not found'}), 404)

    role = (user.role or '').lower() if user else ''

    if role == 'forestry_officer':
        owns_batch = (
            batch.created_by_user_id == user.id
            or can_access_organization(user, batch.current_holder_org_id)
            or can_access_organization(user, batch.source_org_id)
        )
        if not owns_batch:
            return None, (jsonify({'error': 'You are not authorized to view this batch'}), 403)
    elif role in {'transporter', 'mill', 'buyer'}:
        has_custody = can_access_organization(user, batch.current_holder_org_id) or (
            Transaction.query.filter(
                Transaction.batch_id == batch.id,
                (Transaction.from_org_id == user.org_id) | (Transaction.to_org_id == user.org_id),
            ).first() is not None
        )
        if not has_custody and not (
            allow_unassigned_load and role == 'transporter' and batch.current_status == 'harvested'
        ):
            return None, (jsonify({'error': 'You are not authorized to view this batch'}), 403)

    return batch, None
