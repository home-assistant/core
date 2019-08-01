"""Define various utilities for WWLLN tests."""
import pytest

from homeassistant.components.wwlln import CONF_WINDOW, DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_UNIT_SYSTEM,
)

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock WWLLN config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 39.128712,
            CONF_LONGITUDE: -104.9812612,
            CONF_RADIUS: 25,
            CONF_UNIT_SYSTEM: "metric",
            CONF_WINDOW: 3600,
        },
        title="39.128712, -104.9812612",
    )
