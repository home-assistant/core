"""Unit tests the Hass SWITCH component."""

from unittest.mock import AsyncMock

from aiohttp import ClientSession
import pytest

from homeassistant.components.iotty.api import IottyProxy
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import (
    IottyData,
    IottyDataUpdateCoordinator,
)
from homeassistant.components.iotty.switch import IottyLightSwitch, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .conftest import test_ls

from tests.common import MockConfigEntry


async def test_creation_ok(
    mock_iotty: IottyProxy, mock_coordinator: IottyDataUpdateCoordinator
) -> None:
    """Create a hass Switch from existing LS."""

    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])
    assert sut is not None


async def test_device_id_ok(
    mock_iotty: IottyProxy, mock_coordinator: IottyDataUpdateCoordinator
) -> None:
    """Retrieve the nested device_id."""
    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])

    assert sut.device_id == test_ls[0].device_id


async def test_name_ok(
    mock_iotty: IottyProxy, mock_coordinator: IottyDataUpdateCoordinator
) -> None:
    """Retrieve the nested device name."""
    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])

    assert sut.name == test_ls[0].name


async def test_is_on_ok(
    mock_iotty: IottyProxy, mock_coordinator: IottyDataUpdateCoordinator
) -> None:
    """Retrieve the nested status."""
    sut = IottyLightSwitch(mock_coordinator, mock_iotty, test_ls[0])

    test_ls[0].is_on = True

    assert sut.is_on == test_ls[0].is_on


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
    mock_coordinator_store_entity,
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

    assert len(mock_coordinator_store_entity.mock_calls) == 2
