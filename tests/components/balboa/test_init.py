"""Tests of the initialization of the balboa integration."""

from unittest.mock import MagicMock

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import TEST_HOST

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Validate that setup entry also configure the client."""
    assert integration.state == ConfigEntryState.LOADED
    await hass.config_entries.async_unload(integration.entry_id)
    assert integration.state == ConfigEntryState.NOT_LOADED


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

    client.connect.return_value = True
    client.async_configuration_loaded.return_value = False

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
