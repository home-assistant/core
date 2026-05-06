"""Tests for SVS Subwoofer setup/unload."""

from unittest.mock import MagicMock, patch

from homeassistant.components.svs_subwoofer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, SVS_NAME

from tests.common import MockConfigEntry

async def test_setup_and_unload(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """A configured entry sets up, then cleanly unloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
        title=SVS_NAME,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.svs_subwoofer.coordinator.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

async def test_setup_device_not_found(hass: HomeAssistant) -> None:
    """If the BLE device is not in range, setup goes into retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
        title=SVS_NAME,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.svs_subwoofer.coordinator.async_ble_device_from_address",
        return_value=None,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
