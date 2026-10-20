from common import run_seed
from batches import seed_batches
from forest_plots import seed_forest_plots
from organizations import seed_organizations
from permits import seed_permits
from users import seed_users
from vehicles import seed_vehicles


def seed_all():
    seed_organizations()
    seed_forest_plots()
    seed_permits()
    seed_vehicles()
    seed_users()
    seed_batches()
    return 1


if __name__ == '__main__':
    run_seed(seed_all)
