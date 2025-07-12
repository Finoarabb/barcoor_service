import pytest
from app import create_app, mongo

@pytest.fixture(scope='session')
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture(scope='session', autouse=True)
def cleanup(app):
    # Ensure DB is connected now
    try:
        mongo.cx.admin.command('ping') # type: ignore
        mongo.db.reservations.delete_many({}) # type: ignore
        mongo.db.users.delete_many({}) # type: ignore
    except Exception:
        pytest.exit("❌ MongoDB not available or failed to initialize.", returncode=1)
    yield

@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client
