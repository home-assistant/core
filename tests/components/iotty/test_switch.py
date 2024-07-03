"""Unit tests the Hass SWITCH component."""

from unittest.mock import AsyncMock

from aiohttp import ClientSession
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iotty.api import IottyProxy
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import (
    UPDATE_INTERVAL,
    IottyData,
    IottyDataUpdateCoordinator,
)
from homeassistant.components.iotty.switch import IottyLightSwitch, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .conftest import test_ls

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_turn_on_ok(
    hass: HomeAssistant,
    mock_iotty: IottyProxy,
    mock_coordinator: IottyDataUpdateCoordinator,
    mock_iotty_command_fn,
) -> None:
    """Issue a turnon command."""
    mock_iotty.command = AsyncMock()
    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])
    await sut.async_turn_on()
    await hass.async_block_till_done()

    mock_iotty.command.assert_called_once_with(
        test_ls[0].device_id, test_ls[0].cmd_turn_on()
    )


async def test_turn_off_ok(
    hass: HomeAssistant,
    mock_iotty: IottyProxy,
    mock_coordinator: IottyDataUpdateCoordinator,
    mock_iotty_command_fn,
) -> None:
    """Issue a turnoff command."""
    mock_iotty.command = AsyncMock()
    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])
    await sut.async_turn_off()
    await hass.async_block_till_done()

    mock_iotty.command.assert_called_once_with(
        test_ls[0].device_id, test_ls[0].cmd_turn_off()
    )


async def test_setup_entry_wrongdomaindata_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iotty: IottyProxy,
) -> None:
    """Setup the SWITCH entry with empty or wrong DOMAIN data."""

    with pytest.raises(KeyError):
        await async_setup_entry(hass, mock_config_entry, None)

    hass.data.setdefault(DOMAIN, {})
    with pytest.raises(KeyError):
        await async_setup_entry(hass, mock_config_entry, None)


async def test_setup_entry_ok_nodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_add_entities: AddEntitiesCallback,
    local_oauth_impl: ClientSession,
    mock_coordinator: IottyDataUpdateCoordinator,
) -> None:
    """Correctly setup the SWITCH entry, with no iotty Devices to add to Hass."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = mock_coordinator

    mock_coordinator.data = IottyData
    mock_coordinator.data.devices = {}

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(mock_async_add_entities.mock_calls) == 1


async def test_setup_entry_ok_twodevices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_add_entities: AddEntitiesCallback,
    local_oauth_impl: ClientSession,
    mock_coordinator: IottyDataUpdateCoordinator,
) -> None:
    """Correctly setup the SWITCH entry, with two iotty Devices to add to Hass."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = mock_coordinator

    mock_coordinator.data = IottyData
    mock_coordinator.data.devices = test_ls
    mock_coordinator.iotty = IottyProxy

    await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)

    assert len(mock_async_add_entities.mock_calls) == 1


async def test_devices_creaction_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
) -> None:
    """Test iotty switch creation."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.async_entity_ids() == snapshot


async def test_devices_deletion_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_get_devices_twolightswitches_then_one,
    mock_get_status_filled,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test iotty switch deletion."""

    mock_config_entry.add_to_hass(hass)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids() == snapshot
