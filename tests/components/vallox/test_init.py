"""Tests for the Vallox integration setup."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion
from vallox_websocket_api import ValloxApiException

from homeassistant.components.vallox.const import DOMAIN, STATE_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

# Built by the library from the A_CYC_UUID registers in metrics.json.
DEVICE_UUID = "00050006-0007-0008-0009-000a000b000c"


@pytest.mark.usefixtures("init_integration")
async def test_device(
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device of the unit."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_UUID), mock_config_entry.entry_id
    )

    assert device == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_unit_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vallox_client: AsyncMock,
) -> None:
    """Test that setup is retried when the unit cannot be reached."""
    mock_vallox_client.fetch_metric_data.side_effect = ValloxApiException(
        "Unit offline"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_unit_offline_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vallox_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the entities become unavailable while the unit is offline."""
    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ]

    mock_vallox_client.fetch_metric_data.side_effect = ValloxApiException(
        "Unit offline"
    )
    freezer.tick(STATE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {hass.states.get(entity_id).state for entity_id in entity_ids} == {
        STATE_UNAVAILABLE
    }

    mock_vallox_client.fetch_metric_data.side_effect = None
    freezer.tick(STATE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert STATE_UNAVAILABLE not in {
        hass.states.get(entity_id).state for entity_id in entity_ids
    }
