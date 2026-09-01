"""Production configuration: docs gating, CORS, and the config helpers."""
import importlib
import os

import pytest

from src.modules.common.services.config_service import ConfigService


@pytest.fixture
def env(monkeypatch):
    """Set env vars for one test, then restore."""

    def _set(**values):
        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    return _set


# --- ConfigService ----------------------------------------------------------

def test_get_falls_back_to_default(env):
    env(SOME_KEY=None)
    assert ConfigService().get("SOME_KEY", "fallback") == "fallback"


def test_empty_string_is_treated_as_unset(env):
    """An env var set to "" in a compose file must not shadow the default."""
    env(SOME_KEY="")
    assert ConfigService().get("SOME_KEY", "fallback") == "fallback"


@pytest.mark.parametrize("raw,expected", [
    ("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("no", False), ("anything", False),
])
def test_get_bool_parses_common_spellings(env, raw, expected):
    env(FLAG=raw)
    assert ConfigService().get_bool("FLAG") is expected


def test_get_int_falls_back_on_garbage(env):
    env(NUM="not-a-number")
    assert ConfigService().get_int("NUM", 42) == 42


def test_get_list_splits_and_trims(env):
    env(ORIGINS="https://a.com, https://b.com ,")
    assert ConfigService().get_list("ORIGINS") == ["https://a.com", "https://b.com"]


def test_is_production_is_case_insensitive(env):
    env(APP_ENV="PRODUCTION")
    assert ConfigService().is_production is True


def test_defaults_to_development(env):
    env(APP_ENV=None)
    config = ConfigService()
    assert config.env == "development"
    assert config.is_production is False


# --- app wiring -------------------------------------------------------------

def build_app():
    """Rebuild the app so module-level config is re-read."""
    import main

    importlib.reload(main)
    return main.create_app()


def test_docs_are_enabled_in_development(env):
    env(APP_ENV="development", ENABLE_DOCS=None)
    app = build_app()
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"


def test_docs_are_disabled_in_production(env):
    env(APP_ENV="production", ENABLE_DOCS=None)
    app = build_app()
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_docs_can_be_forced_on_in_production(env):
    env(APP_ENV="production", ENABLE_DOCS="true")
    app = build_app()
    assert app.docs_url == "/docs"


def test_cors_is_not_wide_open_in_production_by_default(env):
    env(APP_ENV="production", CORS_ORIGINS=None)
    app = build_app()
    cors = [m for m in app.user_middleware if "CORS" in str(m)]
    assert cors == []  # no origins configured -> middleware not installed


def test_cors_origins_are_read_from_the_environment(env):
    env(APP_ENV="production", CORS_ORIGINS="https://app.example.com")
    app = build_app()
    cors = [m for m in app.user_middleware if "CORS" in str(m)]
    assert len(cors) == 1
    assert cors[0].kwargs["allow_origins"] == ["https://app.example.com"]
