"""Configuration for Google Stackdriver tests."""
import pytest

from homeassistant.components.google_stackdriver import DOMAIN, CONF_KEYFILE


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_KEYFILE: "google_valid_service_account.json"}}
