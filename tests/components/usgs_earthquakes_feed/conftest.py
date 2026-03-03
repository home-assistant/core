"""Configuration for USGS Earthquakes Feed tests."""

import pytest

from homeassistant.components.usgs_earthquakes_feed import (
    CONF_FEED_TYPE,
    CONF_MINIMUM_MAGNITUDE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock USGS Earthquakes Feed config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: -31.0,
            CONF_LONGITUDE: 150.0,
            CONF_FEED_TYPE: "past_hour_m25_earthquakes",
            CONF_RADIUS: 200.0,
            CONF_SCAN_INTERVAL: 300.0,
            CONF_MINIMUM_MAGNITUDE: 0.0,
        },
        title="past_hour_m25_earthquakes",
        unique_id="-31.0, 150.0, past_hour_m25_earthquakes",
    )
