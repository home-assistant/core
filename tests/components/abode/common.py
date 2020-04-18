"""Common methods used across tests for Abode."""
from unittest.mock import patch

from homeassistant.components.abode import DOMAIN as ABODE_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Abode platform."""
    mock_entry = MockConfigEntry(
        domain=ABODE_DOMAIN,
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.abode.ABODE_PLATFORMS", [platform]), patch(
        "abodepy.event_controller.sio"
    ), patch("abodepy.utils.save_cache"):
        assert await async_setup_component(hass, ABODE_DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry
