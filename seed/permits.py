from datetime import date

from common import run_seed, upsert_by
from models import Organization, Permit
from organizations import seed_organizations


PERMITS = [
    {
        'organization_registration_number': 'LOG-001',
        'permit_number': 'PERMIT-2026-001',
        'type': 'harvest',
        'issue_date': date(2026, 1, 1),
        'expiry_date': date(2026, 12, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'TRN-001',
        'permit_number': 'PERMIT-2026-002',
        'type': 'transport',
        'issue_date': date(2026, 1, 1),
        'expiry_date': date(2026, 12, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'LOG-001',
        'permit_number': 'TEST-HARVEST-2026-001',
        'type': 'harvest',
        'issue_date': date(2026, 1, 1),
        'expiry_date': date(2026, 12, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'LOG-001',
        'permit_number': 'TEST-HARVEST-2026-002',
        'type': 'harvest',
        'issue_date': date(2026, 3, 1),
        'expiry_date': date(2027, 2, 28),
        'status': 'active',
    },
    {
        'organization_registration_number': 'LOG-001',
        'permit_number': 'TEST-TRANSPORT-2026-001',
        'type': 'transport',
        'issue_date': date(2026, 1, 1),
        'expiry_date': date(2026, 12, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'LOG-001',
        'permit_number': 'TEST-TRANSPORT-2026-002',
        'type': 'transport',
        'issue_date': date(2026, 4, 1),
        'expiry_date': date(2027, 3, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'TRN-001',
        'permit_number': 'TEST-HARVEST-2026-003',
        'type': 'harvest',
        'issue_date': date(2026, 2, 1),
        'expiry_date': date(2027, 1, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'TRN-001',
        'permit_number': 'TEST-HARVEST-2026-004',
        'type': 'harvest',
        'issue_date': date(2026, 5, 1),
        'expiry_date': date(2027, 4, 30),
        'status': 'active',
    },
    {
        'organization_registration_number': 'TRN-001',
        'permit_number': 'TEST-TRANSPORT-2026-003',
        'type': 'transport',
        'issue_date': date(2026, 2, 1),
        'expiry_date': date(2027, 1, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'TRN-001',
        'permit_number': 'TEST-TRANSPORT-2026-004',
        'type': 'transport',
        'issue_date': date(2026, 6, 1),
        'expiry_date': date(2027, 5, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'REG-001',
        'permit_number': 'TEST-HARVEST-2026-005',
        'type': 'harvest',
        'issue_date': date(2026, 1, 15),
        'expiry_date': date(2027, 1, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'REG-001',
        'permit_number': 'TEST-HARVEST-2026-006',
        'type': 'harvest',
        'issue_date': date(2026, 7, 1),
        'expiry_date': date(2027, 6, 30),
        'status': 'active',
    },
    {
        'organization_registration_number': 'REG-001',
        'permit_number': 'TEST-TRANSPORT-2026-005',
        'type': 'transport',
        'issue_date': date(2026, 1, 15),
        'expiry_date': date(2027, 1, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'REG-001',
        'permit_number': 'TEST-TRANSPORT-2026-006',
        'type': 'transport',
        'issue_date': date(2026, 8, 1),
        'expiry_date': date(2027, 7, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-001',
        'permit_number': 'TEST-HARVEST-2026-007',
        'type': 'harvest',
        'issue_date': date(2026, 3, 15),
        'expiry_date': date(2027, 3, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-001',
        'permit_number': 'TEST-HARVEST-2026-008',
        'type': 'harvest',
        'issue_date': date(2026, 9, 1),
        'expiry_date': date(2027, 8, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-001',
        'permit_number': 'TEST-TRANSPORT-2026-007',
        'type': 'transport',
        'issue_date': date(2026, 3, 15),
        'expiry_date': date(2027, 3, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-001',
        'permit_number': 'TEST-TRANSPORT-2026-008',
        'type': 'transport',
        'issue_date': date(2026, 10, 1),
        'expiry_date': date(2027, 9, 30),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-002',
        'permit_number': 'TEST-HARVEST-2026-009',
        'type': 'harvest',
        'issue_date': date(2026, 4, 15),
        'expiry_date': date(2027, 4, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-002',
        'permit_number': 'TEST-HARVEST-2026-010',
        'type': 'harvest',
        'issue_date': date(2026, 11, 1),
        'expiry_date': date(2027, 10, 31),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-002',
        'permit_number': 'TEST-TRANSPORT-2026-009',
        'type': 'transport',
        'issue_date': date(2026, 4, 15),
        'expiry_date': date(2027, 4, 14),
        'status': 'active',
    },
    {
        'organization_registration_number': 'BUY-002',
        'permit_number': 'TEST-TRANSPORT-2026-010',
        'type': 'transport',
        'issue_date': date(2026, 12, 1),
        'expiry_date': date(2027, 11, 30),
        'status': 'active',
    },
]


def seed_permits():
    seed_organizations()
    for permit in PERMITS:
        organization = Organization.query.filter_by(
            registration_number=permit['organization_registration_number']
        ).one()
        values = {
            'org_id': organization.id,
            'type': permit['type'],
            'issue_date': permit['issue_date'],
            'expiry_date': permit['expiry_date'],
            'status': permit['status'],
        }
        upsert_by(Permit, {'permit_number': permit['permit_number']}, values)
    return len(PERMITS)


if __name__ == '__main__':
    run_seed(seed_permits)
