"""Configuration for Google Stackdriver tests."""
import pytest

from homeassistant.components.google_stackdriver import CONF_KEY_FILE, DOMAIN


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_KEY_FILE: "google_valid_service_account.json"}}
