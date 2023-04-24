"""Common methods used across tests for Roborock."""
from unittest.mock import patch

from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .mock_data import BASE_URL, HOME_DATA, USER_DATA, USER_EMAIL

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Roborock platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data={
            CONF_USERNAME: USER_EMAIL,
            CONF_USER_DATA: USER_DATA.as_dict(),
            CONF_BASE_URL: BASE_URL,
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.roborock.PLATFORMS", [platform]), patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        return_value=HOME_DATA,
    ), patch("homeassistant.components.roborock.RoborockMqttClient.get_networking"):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return mock_entry
