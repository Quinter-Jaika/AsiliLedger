from flask import Flask
from config import Config
from models import db
from auth import init_auth
from routes import init_routes
from sqlalchemy import inspect, text
from blockchain import initialize_chain


REQUIRED_COLUMNS = {
    'timber_batches': {
        'qr_code_path': 'VARCHAR(255) NULL',
        'qr_code_data': 'TEXT NULL',
    },
    'transactions': {
        'from_user_id': 'BIGINT NULL',
        'to_user_id': 'BIGINT NULL',
    },
}


def upgrade_existing_schema():
    """Add model columns to databases created before those columns existed."""
    if db.engine.dialect.name != 'mysql':
        return

    inspector = inspect(db.engine)

    for table, required in REQUIRED_COLUMNS.items():
        existing = {column['name'] for column in inspector.get_columns(table)}
        missing = {name: ddl for name, ddl in required.items() if name not in existing}
        if not missing:
            continue

        with db.engine.begin() as connection:
            for name, ddl in missing.items():
                connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))


def upgrade_existing_roles():
    """Rename the legacy 'logger' role to 'forestry_officer' on existing databases."""
    if db.engine.dialect.name != 'mysql':
        return

    with db.engine.begin() as connection:
        legacy_id = connection.execute(
            text("SELECT id FROM roles WHERE name = 'logger'")
        ).scalar()
        if legacy_id is None:
            return

        current_id = connection.execute(
            text("SELECT id FROM roles WHERE name = 'forestry_officer'")
        ).scalar()

        if current_id is None:
            connection.execute(
                text("UPDATE roles SET name = 'forestry_officer' WHERE id = :legacy_id"),
                {'legacy_id': legacy_id},
            )
            return

        # Both roles exist, so move memberships across before dropping the legacy row.
        connection.execute(
            text('UPDATE IGNORE user_roles SET role_id = :current_id WHERE role_id = :legacy_id'),
            {'current_id': current_id, 'legacy_id': legacy_id},
        )
        connection.execute(
            text('DELETE FROM user_roles WHERE role_id = :legacy_id'),
            {'legacy_id': legacy_id},
        )
        connection.execute(
            text('DELETE FROM roles WHERE id = :legacy_id'),
            {'legacy_id': legacy_id},
        )

def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    db.init_app(app)
    init_auth(app)
    init_routes(app)
    with app.app_context():
        db.create_all()  # create tables on first run
        upgrade_existing_schema()
        upgrade_existing_roles()
        initialize_chain()
    return app

if __name__ == "__main__":
    create_app().run(debug=True)