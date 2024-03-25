"""Common methods used across tests for HaFAS."""
from unittest.mock import patch

from homeassistant.components.hafas.const import (
    CONF_DESTINATION,
    CONF_ONLY_DIRECT,
    CONF_PROFILE,
    CONF_START,
    DOMAIN,
)
from homeassistant.const import CONF_OFFSET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import (
    TEST_OFFSET,
    TEST_ONLY_DIRECT,
    TEST_PROFILE,
    TEST_STATION1,
    TEST_STATION2,
    TEST_TIME,
)

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Abode platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROFILE: TEST_PROFILE,
            CONF_START: TEST_STATION1,
            CONF_DESTINATION: TEST_STATION2,
            CONF_OFFSET: TEST_OFFSET,
            CONF_ONLY_DIRECT: TEST_ONLY_DIRECT,
        },
    )
    mock_entry.add_to_hass(hass)

    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))
    with patch("homeassistant.core.dt_util.utcnow", return_value=TEST_TIME):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry
