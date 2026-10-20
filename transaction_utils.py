import hashlib
import json


def hash_transaction(transaction):
    payload = {
        'transaction_id': transaction.id,
        'batch_id': transaction.batch_id,
        'event_type': transaction.event_type,
        'event_status': transaction.event_status,
        'initiated_by_user_id': transaction.initiated_by_user_id,
        'from_user_id': transaction.from_user_id,
        'to_user_id': transaction.to_user_id,
        'from_org_id': transaction.from_org_id,
        'to_org_id': transaction.to_org_id,
        'vehicle_id': transaction.vehicle_id,
        'permit_id': transaction.permit_id,
        'quantity_m3': str(transaction.quantity_m3) if transaction.quantity_m3 is not None else None,
        'weight_kg': str(transaction.weight_kg) if transaction.weight_kg is not None else None,
        'occurred_at': transaction.occurred_at.isoformat() if transaction.occurred_at else None,
        'location_lat': transaction.location_lat,
        'location_lon': transaction.location_lon,
        'notes': transaction.notes,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()