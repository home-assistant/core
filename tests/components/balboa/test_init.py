"""Tests of the initialization of the balboa integration."""

from unittest.mock import MagicMock

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import TEST_HOST, init_integration

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, client: MagicMock) -> None:
    """Validate that setup entry also configure the client."""
    config_entry = await init_integration(hass)

    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_fails(hass: HomeAssistant, client: MagicMock) -> None:
    """Validate that setup entry also configure the client."""
    config_entry = MockConfigEntry(
        domain=BALBOA_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
        },
    )
    config_entry.add_to_hass(hass)

    client.connect.return_value = False

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
