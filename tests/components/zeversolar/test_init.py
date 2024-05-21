"""Test the init file code."""

import pytest

import homeassistant.components.zeversolar.__init__ as init
from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, MockModule, mock_integration


async def test_async_setup_entry_fails(hass: HomeAssistant) -> None:
    """Test the sensor setup."""
    mock_integration(hass, MockModule(DOMAIN))

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
            "data": "test",
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(
            DOMAIN,
            {
                "data": "test2",
            },
        )

    config.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady):
        await init.async_setup_entry(hass, config)
