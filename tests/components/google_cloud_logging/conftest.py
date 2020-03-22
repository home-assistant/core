"""Configuration for Google Cloud Logging tests."""
import pytest

from homeassistant.components.google_cloud_logging import CONF_KEY_FILE, DOMAIN


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_KEY_FILE: "google_valid_service_account.json"}}
