"""Test the init file code."""

import pytest

import homeassistant.components.zeversolar.__init__ as init
from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, MockModule, mock_integration

MOCK_HOST_ZEVERSOLAR = "zeversolar-fake-host"
MOCK_PORT_ZEVERSOLAR = 10200


async def test_async_setup_entry_fails(hass: HomeAssistant) -> None:
    """Test the sensor setup."""
    mock_integration(hass, MockModule(DOMAIN))

    config = MockConfigEntry(
        data={
            CONF_HOST: MOCK_HOST_ZEVERSOLAR,
            CONF_PORT: MOCK_PORT_ZEVERSOLAR,
        },
        domain=DOMAIN,
    )

    config.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady):
        await init.async_setup_entry(hass, config)
