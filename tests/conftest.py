from __future__ import annotations

import pytest
from helpers import SECRET, Client, FakeFacebook, FakeHTTP, FakeX

from aisocial import create_app, i18n
from aisocial.config import Settings
from aisocial.platforms import LinkedInPlatform


@pytest.fixture(autouse=True)
def _english_after_each_test():
    """The language is process-wide: a test that switches to Greek must not leak into the next one."""
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def make_settings(tmp_path, **env):
    values = {"APP_SECRET": SECRET, "AISOCIAL_DB_PATH": str(tmp_path / "aisocial.db")}
    values.update(env)
    return Settings.from_env(values)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def platforms():
    return {"x": FakeX(), "linkedin": LinkedInPlatform(http=FakeHTTP()), "facebook": FakeFacebook()}


@pytest.fixture
def app(settings, platforms):
    # The scheduler thread is never started in tests; they call scheduler.tick() directly.
    return create_app(settings, platforms=platforms, start_scheduler=False)


@pytest.fixture
def client(app):
    return Client(app)


@pytest.fixture
def new_app(tmp_path, platforms):
    """Build another app on the same data folder (e.g. a restart with other settings)."""

    def build(**env):
        return create_app(make_settings(tmp_path, **env), platforms=platforms, start_scheduler=False)

    return build
