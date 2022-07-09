"""Common setup for fibaro tests."""
from unittest.mock import patch

from homeassistant.components.fibaro.const import CONF_IMPORT_PLUGINS, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import TEST_PASSWORD, TEST_URL, TEST_USERNAME

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up the fibaro platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: True,
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.fibaro.PLATFORMS", platforms), patch(
        "homeassistant.components.fibaro.StateHandlerV4",
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return mock_entry
