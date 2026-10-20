from common import run_seed, upsert_by
from models import ForestPlot, Organization
from organizations import seed_organizations


FOREST_PLOTS = [
    {
        'organization_registration_number': 'LOG-001',
        'forest_name': 'Mau Timber Block 1',
        'location_lat': -0.4415,
        'location_lon': 35.4102,
        'approved_capacity_hectares': 96.5,
    },
    {
        'organization_registration_number': 'LOG-001',
        'forest_name': 'Mau Timber Block 2',
        'location_lat': -0.4702,
        'location_lon': 35.4519,
        'approved_capacity_hectares': 74.0,
    },
    {
        'organization_registration_number': 'KFS-001',
        'forest_name': 'Mau East Block A',
        'location_lat': -0.4632,
        'location_lon': 35.4420,
        'approved_capacity_hectares': 1250.0,
    },
    {
        'organization_registration_number': 'KFS-001',
        'forest_name': 'Kakamega Community Forest',
        'location_lat': 0.2827,
        'location_lon': 34.7519,
        'approved_capacity_hectares': 480.0,
    },
   {
          'organization_registration_number': 'LOG-002',
        'forest_name': 'Green Ridge Plot A',
        'location_lat': -0.303100,
        'location_lon': 36.080000,
        'approved_capacity_hectares': 24.50,
    },
    {
        'organization_registration_number': 'LOG-002',
        'forest_name': 'Green Ridge Plot B',
        'location_lat': -0.315200,
        'location_lon': 36.092800,
        'approved_capacity_hectares': 18.75,
    },
    {
        'organization_registration_number': 'LOG-002',
        'forest_name': 'Green Ridge Plot C',
        'location_lat': -0.289400,
        'location_lon': 36.061100,
        'approved_capacity_hectares': 31.20,
    },
    {
        'organization_registration_number': 'LOG-002',
        'forest_name': 'Green Ridge Plot D',
        'location_lat': -0.341700,
        'location_lon': 36.104500,
        'approved_capacity_hectares': 12.80,
    },
    {
        'organization_registration_number': 'LOG-003',
        'forest_name': 'Mau Summit Plot 1',
        'location_lat': -0.220300,
        'location_lon': 35.578200,
        'approved_capacity_hectares': 42.00,
    },
    {
        'organization_registration_number': 'LOG-003',
        'forest_name': 'Mau Summit Plot 2',
        'location_lat': -0.245100,
        'location_lon': 35.601900,
        'approved_capacity_hectares': 28.60,
    },
    {
        'organization_registration_number': 'LOG-003',
        'forest_name': 'Mau Summit Plot 3',
        'location_lat': -0.201800,
        'location_lon': 35.552400,
        'approved_capacity_hectares': 35.40,
    },
    {
        'organization_registration_number': 'LOG-003',
        'forest_name': 'Mau Summit Plot 4',
        'location_lat': -0.268700,
        'location_lon': 35.629100,
        'approved_capacity_hectares': 19.90,
    },
    {
        'organization_registration_number': 'LOG-004',
        'forest_name': 'Kericho Plot K1',
        'location_lat': -0.368900,
        'location_lon': 35.286500,
        'approved_capacity_hectares': 22.30,
    },
    {
        'organization_registration_number': 'LOG-004',
        'forest_name': 'Kericho Plot K2',
        'location_lat': -0.391200,
        'location_lon': 35.314800,
        'approved_capacity_hectares': 16.70,
    },
    {
        'organization_registration_number': 'LOG-004',
        'forest_name': 'Kericho Plot K3',
        'location_lat': -0.350600,
        'location_lon': 35.251100,
        'approved_capacity_hectares': 27.10,
    },
    {
        'organization_registration_number': 'LOG-004',
        'forest_name': 'Kericho Plot K4',
        'location_lat': -0.414300,
        'location_lon': 35.338700,
        'approved_capacity_hectares': 14.25,
    },
    {
        'organization_registration_number': 'LOG-005',
        'forest_name': 'Aberdare Plot Alpha',
        'location_lat': -0.418200,
        'location_lon': 36.734100,
        'approved_capacity_hectares': 38.50,
    },
    {
        'organization_registration_number': 'LOG-005',
        'forest_name': 'Aberdare Plot Beta',
        'location_lat': -0.447800,
        'location_lon': 36.761200,
        'approved_capacity_hectares': 25.80,
    },
    {
        'organization_registration_number': 'LOG-005',
        'forest_name': 'Aberdare Plot Gamma',
        'location_lat': -0.389500,
        'location_lon': 36.708900,
        'approved_capacity_hectares': 29.60,
    },
    {
        'organization_registration_number': 'LOG-005',
        'forest_name': 'Aberdare Plot Delta',
        'location_lat': -0.476100,
        'location_lon': 36.792400,
        'approved_capacity_hectares': 17.40,
    },
    {
        'organization_registration_number': 'LOG-006',
        'forest_name': 'Coastal Plot C1',
        'location_lat': -3.943600,
        'location_lon': 39.764200,
        'approved_capacity_hectares': 33.75,
    },
    {
        'organization_registration_number': 'LOG-006',
        'forest_name': 'Coastal Plot C2',
        'location_lat': -3.981100,
        'location_lon': 39.801500,
        'approved_capacity_hectares': 21.90,
    },
    {
        'organization_registration_number': 'LOG-006',
        'forest_name': 'Coastal Plot C3',
        'location_lat': -3.912800,
        'location_lon': 39.726700,
        'approved_capacity_hectares': 26.40,
    },
    {
        'organization_registration_number': 'LOG-006',
        'forest_name': 'Coastal Plot C4',
        'location_lat': -4.023400,
        'location_lon': 39.839100,
        'approved_capacity_hectares': 15.60,
    },
]


def seed_forest_plots():
    seed_organizations()
    for plot in FOREST_PLOTS:
        organization = Organization.query.filter_by(
            registration_number=plot['organization_registration_number']
        ).one()
        values = {
            'org_id': organization.id,
            'location_lat': plot['location_lat'],
            'location_lon': plot['location_lon'],
            'approved_capacity_hectares': plot['approved_capacity_hectares'],
        }
        upsert_by(ForestPlot, {'forest_name': plot['forest_name']}, values)
    return len(FOREST_PLOTS)


if __name__ == '__main__':
    run_seed(seed_forest_plots)
