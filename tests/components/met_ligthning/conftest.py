"""Define various utilities for Met lightning tests."""
import pytest

from homeassistant.components.met_lightning import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock Met lightning config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LATITUDE: 39.128712, CONF_LONGITUDE: -104.9812612, CONF_RADIUS: 25},
        title="39.128712, -104.9812612",
    )
