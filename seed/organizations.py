from common import run_seed, upsert_by
from models import Organization


ORGANIZATIONS = [
    {
        'name': 'Kenya Forest Service',
        'type': 'KFS',
        'registration_number': 'KFS-001',
        'contact': 'kfs@example.org',
    },
    {
        'name': 'Mau Timber Harvesters',
        'type': 'logger',
        'registration_number': 'LOG-001',
        'contact': 'harvesters@example.org',
    },
    {
        'name': 'Savanna Timber Transport',
        'type': 'transporter',
        'registration_number': 'TRN-001',
        'contact': 'transport@example.org',
    },
    {
        'name': 'Nairobi Timber Mill',
        'type': 'mill',
        'registration_number': 'MIL-001',
        'contact': 'mill@example.org',
    },
    {
        'name': 'East Africa Timber Buyers',
        'type': 'buyer',
        'registration_number': 'BUY-001',
        'contact': 'buyers@example.org',
    },
    {
        'name': 'Green Ridge Forestry Cooperative',
        'type': 'logger',
        'registration_number': 'LOG-002',
        'contact': 'info@greenridge.org',
    },
    {
        'name': 'Mau Summit Timber Group',
        'type': 'logger',
        'registration_number': 'LOG-003',
        'contact': 'office@mausummit.org',
    },
    {
        'name': 'Kericho Forest Works Ltd',
        'type': 'logger',
        'registration_number': 'LOG-004',
        'contact': 'admin@kerichoforest.org',
    },
    {
        'name': 'Aberdare Timber Collective',
        'type': 'logger',
        'registration_number': 'LOG-005',
        'contact': 'contact@aberdaretimber.org',
    },
    {
        'name': 'Coastal Woodland Enterprises',
        'type': 'logger',
        'registration_number': 'LOG-006',
        'contact': 'hello@coastalwoodland.org',
    },
    {
        'name': 'Highland Timber Transport Ltd',
        'type': 'transporter',
        'registration_number': 'TRN-002',
        'contact': 'dispatch@highlandtransport.org',
    },
    {
        'name': 'Rift Valley Haulers Ltd',
        'type': 'transporter',
        'registration_number': 'TRN-003',
        'contact': 'ops@riftvalleyhaulers.org',
    },
    {
        'name': 'Savanna Logistics Ltd',
        'type': 'transporter',
        'registration_number': 'TRN-004',
        'contact': 'bookings@savannalogistics.org',
    },
    {
        'name': 'Eastern Freight Services Ltd',
        'type': 'transporter',
        'registration_number': 'TRN-005',
        'contact': 'control@easternfreight.org',
    },
    {
        'name': 'Nairobi Wood Processors Ltd',
        'type': 'mill',
        'registration_number': 'MIL-002',
        'contact': 'operations@nairobiwood.org',
    },
    {
        'name': 'Central Highlands Sawmill Ltd',
        'type': 'mill',
        'registration_number': 'MIL-003',
        'contact': 'mill@centralhighlands.org',
    },
    {
        'name': 'Lake Basin Timber Products Ltd',
        'type': 'mill',
        'registration_number': 'MIL-004',
        'contact': 'production@lakebasin.org',
    },
    {
        'name': 'Timber Trace Regulatory Office',
        'type': 'inspector',
        'registration_number': 'REG-001',
        'contact': 'inspector@timbertrace.org',
    },
    {
        'name': 'Western Region Forest Authority',
        'type': 'inspector',
        'registration_number': 'REG-002',
        'contact': 'western@forestauthority.org',
    },
    {
        'name': 'Eastern Region Forest Authority',
        'type': 'inspector',
        'registration_number': 'REG-003',
        'contact': 'eastern@forestauthority.org',
    },
    {
        'name': 'Kenya Timber Trade Demo Buyer',
        'type': 'buyer',
        'registration_number': 'BUY-002',
        'contact': 'buyer@timbertrace.org',
    },
    {
        'name': 'Nairobi Builders Merchants Ltd',
        'type': 'buyer',
        'registration_number': 'BUY-003',
        'contact': 'purchasing@nbm.org',
    },
    {
        'name': 'Mombasa Construction Supplies Ltd',
        'type': 'buyer',
        'registration_number': 'BUY-004',
        'contact': 'orders@mombasasupplies.org',
    },
    {
        'name': 'Eldoret Hardware & Timber Ltd',
        'type': 'buyer',
        'registration_number': 'BUY-005',
        'contact': 'sales@eldorethardware.org',
    },
    {
        'name': 'Kisumu Trade & Timber Ltd',
        'type': 'buyer',
        'registration_number': 'BUY-006',
        'contact': 'trade@kisumutimber.org',
    },
]


def seed_organizations():
    for organization in ORGANIZATIONS:
        registration_number = organization['registration_number']
        upsert_by(
            Organization,
            {'registration_number': registration_number},
            organization,
        )
    return len(ORGANIZATIONS)


if __name__ == '__main__':
    run_seed(seed_organizations)
