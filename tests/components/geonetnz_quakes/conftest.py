"""Configuration for GeoNet NZ Quakes tests."""
import pytest

from homeassistant.components.geonetnz_quakes import (
    CONF_MINIMUM_MAGNITUDE,
    CONF_MMI,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
)

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock GeoNet NZ Quakes config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
            CONF_UNIT_SYSTEM: "metric",
            CONF_SCAN_INTERVAL: 300.0,
            CONF_MMI: 4,
            CONF_MINIMUM_MAGNITUDE: 0.0,
        },
        title="-41.2, 174.7",
        unique_id="-41.2, 174.7",
    )
