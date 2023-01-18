"""Configuration for NSW Rural Fire Service Feeds tests."""
import pytest

from homeassistant.components.nsw_rural_fire_service_feed.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry():
    """Create a mock NSW Rural Fire Service Feeds Events config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
        },
        title="-41.2, 174.7",
        unique_id="-41.2, 174.7",
    )
