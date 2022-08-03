"""Common methods used across tests for Aqara."""
from unittest.mock import patch

from homeassistant.components.aqara import DOMAIN as AQARA_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_HOST
from homeassistant.setup import async_setup_component
from homeassistant.components.aqara import CONF_COUNTRY_CODE

from tests.common import MockConfigEntry

# pytest ./tests/components/<your_component>/ --cov=homeassistant.components.<your_component> --cov-report term-missing -vv


async def setup_platform(hass, platform):
    """Set up the aqara platform."""
    mock_entry = MockConfigEntry(
        domain=AQARA_DOMAIN,
        data={
            CONF_HOST: "https://open-cn.aqara.com",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_COUNTRY_CODE: "86",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.aqara.PLATFORMS", [platform]):
        assert await async_setup_component(hass, AQARA_DOMAIN, {})
    await hass.async_block_till_done()


def mock_start(self):
    print("mock_start called")
    return
