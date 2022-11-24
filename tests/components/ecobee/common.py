"""Common methods used across tests for Ecobee."""
from unittest.mock import patch

from spencerassistant.components.ecobee.const import CONF_REFRESH_TOKEN, DOMAIN
from spencerassistant.const import CONF_API_KEY
from spencerassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the ecobee platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "ABC123",
            CONF_REFRESH_TOKEN: "EFG456",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("spencerassistant.components.ecobee.const.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    return mock_entry
