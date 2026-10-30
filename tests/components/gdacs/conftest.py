"""Configuration for GDACS tests."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gdacs.const import DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock GDACS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCATION: {
                CONF_LATITUDE: -41.2,
                CONF_LONGITUDE: 174.7,
                CONF_RADIUS: 25000,
            }
        },
        title="Global Disaster Alert and Coordination System",
        unique_id="-41.2, 174.7",
        version=2,
    )
