from common import run_seed, upsert_by
from models import Organization, Vehicle
from organizations import seed_organizations


VEHICLES = [
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDA 482A',
        'capacity_m3': 32.0,
        'current_location': 'Nakuru',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDB 719B',
        'capacity_m3': 24.0,
        'current_location': 'Nairobi',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDD 123A',
        'capacity_m3': 18.0,
        'current_location': 'Nairobi Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDD 124B',
        'capacity_m3': 22.5,
        'current_location': 'Nakuru Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDD 125C',
        'capacity_m3': 15.0,
        'current_location': 'Eldoret Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDD 126D',
        'capacity_m3': 25.0,
        'current_location': 'Green Ridge Collection Point',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDD 127E',
        'capacity_m3': 20.0,
        'current_location': 'Mau Summit Loading Bay',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDE 201F',
        'capacity_m3': 19.5,
        'current_location': 'Nakuru Yard',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDE 202G',
        'capacity_m3': 24.0,
        'current_location': 'Kericho Yard',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDE 203H',
        'capacity_m3': 16.5,
        'current_location': 'Bomet Yard',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDE 204J',
        'capacity_m3': 28.0,
        'current_location': 'Mau Summit Collection Point',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDE 205K',
        'capacity_m3': 21.0,
        'current_location': 'Kericho Collection Point',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDF 311L',
        'capacity_m3': 17.0,
        'current_location': 'Nairobi South Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDF 312M',
        'capacity_m3': 23.5,
        'current_location': 'Thika Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDF 313N',
        'capacity_m3': 26.0,
        'current_location': 'Aberdare Loading Bay',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDF 314P',
        'capacity_m3': 18.5,
        'current_location': 'Nairobi Yard',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDF 315Q',
        'capacity_m3': 20.5,
        'current_location': 'Thika Collection Point',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDG 421R',
        'capacity_m3': 22.0,
        'current_location': 'Mombasa Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDG 422S',
        'capacity_m3': 25.5,
        'current_location': 'Voi Yard',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDG 423T',
        'capacity_m3': 16.0,
        'current_location': 'Malindi Depot',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDG 424U',
        'capacity_m3': 27.0,
        'current_location': 'Coastal Plot C1 Loading Bay',
    },
    {
        'organization_registration_number': 'TRN-001',
        'plate_number': 'KDG 425V',
        'capacity_m3': 19.0,
        'current_location': 'Mombasa Collection Point',
    },
]


def seed_vehicles():
    seed_organizations()
    for vehicle in VEHICLES:
        organization = Organization.query.filter_by(
            registration_number=vehicle['organization_registration_number']
        ).one()
        values = {
            'owner_org_id': organization.id,
            'capacity_m3': vehicle['capacity_m3'],
            'current_location': vehicle['current_location'],
        }
        upsert_by(Vehicle, {'plate_number': vehicle['plate_number']}, values)
    return len(VEHICLES)


if __name__ == '__main__':
    run_seed(seed_vehicles)
