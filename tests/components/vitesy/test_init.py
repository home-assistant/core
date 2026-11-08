"""Test the Vitesy integration setup and teardown."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiovitesy.api import VitesyDevice
from aiovitesy.exceptions import CannotAuthenticate, CannotConnect, VitesyError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.vitesy.const import DOMAIN
from homeassistant.components.vitesy.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials during setup start a reauth flow."""
    mock_vitesy_client.login.side_effect = CannotAuthenticate
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_connection_failure_is_retried(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a transient connection error triggers a setup retry."""
    mock_vitesy_client.login.side_effect = CannotConnect
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed refresh marks the entities unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_vitesy_client.get_all_devices.side_effect = VitesyError("boom")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.kitchen_shelfy_air_quality_score").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("method", ["get_all_devices", "get_mode_status"])
async def test_update_auth_failure(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test rejected credentials during a refresh start a reauth flow."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_vitesy_client, method).side_effect = CannotAuthenticate
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not mock_config_entry.runtime_data.last_update_success
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_removed_device_is_removed_from_registry(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device removed from the account is removed from Home Assistant."""
    removed_device_id = "80:65:99:34:F9:B5"
    mock_devices[removed_device_id] = replace(
        mock_devices[DEVICE_ID], device_id=removed_device_id, name="Living room Shelfy"
    )
    await setup_integration(hass, mock_config_entry)
    identifier = (DOMAIN, removed_device_id)
    assert device_registry.async_get_device_by_identifier(
        identifier, mock_config_entry.entry_id
    )

    del mock_devices[removed_device_id]
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device_by_identifier(
        identifier, mock_config_entry.entry_id
    )
    assert not entity_registry.async_get("sensor.living_room_shelfy_air_quality_score")
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
