"""Keep ordinary tests away from hosting credentials in the shell environment."""
import pytest


@pytest.fixture(autouse=True)
def isolate_hosting_environment(monkeypatch):
    # Integration fixtures deliberately set a disposable PostgreSQL URL after
    # this fixture. A production DATABASE_URL must never be the test default.
    for name in ('DATABASE_URL', 'RENDER', 'EW_PHOTO_STORAGE', 'EW_DATA_DIR',
                 'EW_SECURE_COOKIES', 'EW_DB_SCHEMA'):
        monkeypatch.delenv(name, raising=False)
