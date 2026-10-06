import pytest
from app.database import Database, postgres_query
from app.server import create_app


def test_render_refuses_ephemeral_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='Render requires DATABASE_URL'):
        Database(tmp_path/'jobs.sqlite3')


def test_render_requires_remote_photos(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    monkeypatch.setenv('EW_PHOTO_STORAGE', 'local')
    with pytest.raises(ValueError, match='EW_PHOTO_STORAGE=r2'):
        Database(tmp_path/'jobs.sqlite3')


def test_invalid_url_never_falls_back_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'https://invalid.test/secret')
    with pytest.raises(ValueError, match='PostgreSQL connection URL'):
        create_app(tmp_path)
    assert not (tmp_path/'jobs.sqlite3').exists()


def test_query_parameters_keep_literals_and_percent_signs():
    query = '''SELECT 'Why? 50%', 'it''s?', "field?", 7 % 2 WHERE email=?'''
    assert postgres_query(query) == '''SELECT 'Why? 50%%', 'it''s?', "field?", 7 %% 2 WHERE email=%s'''
