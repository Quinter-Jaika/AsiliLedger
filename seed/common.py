import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from models import db


def run_seed(seed_function):
    app = create_app()
    with app.app_context():
        db.create_all()
        count = seed_function()
        db.session.commit()
        print(f'{seed_function.__name__}: {count} records ready')


def upsert_by(model, lookup, values):
    record = model.query.filter_by(**lookup).first()
    if record is None:
        attributes = dict(lookup)
        attributes.update(values)
        record = model(**attributes)
        db.session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    return record
