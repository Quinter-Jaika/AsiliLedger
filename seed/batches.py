from datetime import date, datetime, time, timedelta

from common import run_seed, upsert_by
from forest_plots import seed_forest_plots
from models import db, ForestPlot, Organization, Permit, TimberBatch, Transaction, User, Vehicle
from organizations import seed_organizations
from permits import seed_permits
from users import seed_users
from vehicles import seed_vehicles


# Each event moves custody to the next organization, so the last event sets the batch status.
EVENT_FLOW = {
    'harvest': {'actor': 'forestry_officer', 'to': 'owner', 'status': 'harvested'},
    'load': {'actor': 'transporter', 'to': 'transporter', 'status': 'in_transit'},
    'unload': {'actor': 'transporter', 'to': 'mill', 'status': 'at_destination'},
    'process': {'actor': 'mill', 'to': 'mill', 'status': 'at_mill'},
    'sale': {'actor': 'mill', 'to': 'buyer', 'status': 'sold'},
}

BATCHES = [
    {
        'unique_tag_id': 'TEST-2026-001',
        'species': 'Mahogany',
        'volume_m3': 18.5,
        'weight_kg': 12400.0,
        'harvest_date': date(2026, 9, 1),
        'plot': 'Mau Timber Block 1',
        'events': ['harvest'],
    },
    {
        'unique_tag_id': 'TEST-2026-002',
        'species': 'Teak',
        'volume_m3': 24.0,
        'weight_kg': 16800.0,
        'harvest_date': date(2026, 9, 4),
        'plot': 'Mau Timber Block 2',
        'events': ['harvest', 'load'],
    },
    {
        'unique_tag_id': 'TEST-2026-003',
        'species': 'Cypress, Pine',
        'volume_m3': 31.25,
        'weight_kg': 20100.0,
        'harvest_date': date(2026, 9, 7),
        'plot': 'Mau Summit Plot 1',
        'events': ['harvest', 'load', 'unload'],
    },
    {
        'unique_tag_id': 'TEST-2026-004',
        'species': 'Eucalyptus',
        'volume_m3': 12.75,
        'weight_kg': 8600.0,
        'harvest_date': date(2026, 9, 10),
        'plot': 'Kericho Plot K1',
        'events': ['harvest', 'load', 'unload', 'process'],
    },
    {
        'unique_tag_id': 'TEST-2026-005',
        'species': 'Grevillea',
        'volume_m3': 27.4,
        'weight_kg': 18250.0,
        'harvest_date': date(2026, 9, 12),
        'plot': 'Aberdare Plot Alpha',
        'events': ['harvest', 'load', 'unload', 'process', 'sale'],
    },
    {
        'unique_tag_id': 'TEST-2026-006',
        'species': 'Camphor',
        'volume_m3': 9.8,
        'weight_kg': 6400.0,
        'harvest_date': date(2026, 9, 15),
        'plot': 'Coastal Plot C1',
        'events': ['harvest'],
    },
]


def _rebuild_custody_chain(batch, spec, plot, owner_org, actors, orgs, vehicle, permit):
    """Replace the seeded batch's events so re-running produces the same chain."""
    Transaction.query.filter_by(batch_id=batch.id).delete()

    started_at = datetime.combine(spec['harvest_date'], time(7, 30))
    previous_org = owner_org
    previous_actor = actors['forestry_officer']

    for offset, event_type in enumerate(spec['events']):
        flow = EVENT_FLOW[event_type]
        actor = actors[flow['actor']]
        to_org = owner_org if flow['to'] == 'owner' else orgs[flow['to']]

        db.session.add(Transaction(
            batch_id=batch.id,
            event_type=event_type,
            initiated_by_user_id=actor.id,
            from_user_id=previous_actor.id,
            to_user_id=actor.id,
            from_org_id=previous_org.id,
            to_org_id=to_org.id,
            vehicle_id=vehicle.id if event_type in ('load', 'unload') else None,
            permit_id=permit.id if (permit and event_type == 'harvest') else None,
            quantity_m3=spec['volume_m3'],
            weight_kg=spec['weight_kg'],
            occurred_at=started_at + timedelta(days=offset, hours=offset * 2),
            location_lat=round((plot.location_lat or 0.0) + offset * 0.012, 6),
            location_lon=round((plot.location_lon or 0.0) + offset * 0.015, 6),
            notes=f'Seeded {event_type} event for {spec["unique_tag_id"]}',
        ))

        previous_org = to_org
        previous_actor = actor

    batch.current_status = EVENT_FLOW[spec['events'][-1]]['status']
    batch.current_holder_org_id = previous_org.id


def seed_batches():
    seed_organizations()
    seed_forest_plots()
    seed_permits()
    seed_vehicles()
    seed_users()
    db.session.flush()

    actors = {
        'forestry_officer': User.query.filter_by(email='logger@asililedger.local').one(),
        'transporter': User.query.filter_by(email='transporter@asililedger.local').one(),
        'mill': User.query.filter_by(email='mill@asililedger.local').one(),
        'buyer': User.query.filter_by(email='buyer@asililedger.local').one(),
    }
    orgs = {
        'transporter': Organization.query.filter_by(registration_number='TRN-001').one(),
        'mill': Organization.query.filter_by(registration_number='MIL-001').one(),
        'buyer': Organization.query.filter_by(registration_number='BUY-001').one(),
    }
    vehicle = Vehicle.query.filter_by(plate_number='KDA 482A').one()

    for spec in BATCHES:
        plot = ForestPlot.query.filter_by(forest_name=spec['plot']).one()
        owner_org = db.session.get(Organization, plot.org_id)
        permit = Permit.query.filter_by(
            org_id=owner_org.id, type='harvest', status='active'
        ).first()

        batch = upsert_by(
            TimberBatch,
            {'unique_tag_id': spec['unique_tag_id']},
            {
                'species': spec['species'],
                'volume_m3': spec['volume_m3'],
                'weight_kg': spec['weight_kg'],
                'harvest_date': spec['harvest_date'],
                'plot_id': plot.id,
                'permit_id': permit.id if permit else None,
                'source_org_id': owner_org.id,
                'created_by_user_id': actors['forestry_officer'].id,
                'current_holder_org_id': owner_org.id,
            },
        )
        db.session.flush()

        _rebuild_custody_chain(batch, spec, plot, owner_org, actors, orgs, vehicle, permit)

    return len(BATCHES)


if __name__ == '__main__':
    run_seed(seed_batches)
