"""Tests for the Hydrawise integration."""

from copy import deepcopy
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller, User, Zone

from homeassistant.components.hydrawise.const import DOMAIN, MAIN_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connect_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: AsyncMock
) -> None:
    """Test that a connection error triggers a retry."""
    mock_pydrawise.get_user.side_effect = ClientError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_version(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test updating to the GaphQL API works."""
    mock_config_entry_legacy.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_legacy.state is ConfigEntryState.SETUP_ERROR

    # Make sure reauth flow has been initiated
    assert any(mock_config_entry_legacy.async_get_active_flows(hass, {"reauth"}))


async def test_auto_add_devices(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    user: User,
    controller: Controller,
    zones: list[Zone],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are auto-added to the device registry."""
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(controller.id))}
    )
    assert device is not None
    for zone in zones:
        zone_device = device_registry.async_get_device(
            identifiers={(DOMAIN, str(zone.id))}
        )
        assert zone_device is not None
    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    # 1 controller + 2 zones
    assert len(all_devices) == 3

    controller2 = deepcopy(controller)
    controller2.id += 10
    controller2.name += " 2"
    controller2.sensors = []

    zones2 = deepcopy(zones)
    for zone in zones2:
        zone.id += 10
        zone.name += " 2"

    user.controllers = [controller, controller2]
    mock_pydrawise.get_zones.side_effect = [zones, zones2]

    # Make the coordinator refresh data.
    freezer.tick(MAIN_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    new_controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(controller2.id))}
    )
    assert new_controller_device is not None
    for zone in zones2:
        new_zone_device = device_registry.async_get_device(
            identifiers={(DOMAIN, str(zone.id))}
        )
        assert new_zone_device is not None

    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    # 2 controllers + 4 zones
    assert len(all_devices) == 6


async def test_auto_remove_devices(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: MockConfigEntry,
    user: User,
    controller: Controller,
    zones: list[Zone],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test old devices are auto-removed from the device registry."""
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, str(controller.id))})
        is not None
    )
    for zone in zones:
        device = device_registry.async_get_device(identifiers={(DOMAIN, str(zone.id))})
        assert device is not None

    user.controllers = []
    # Make the coordinator refresh data.
    freezer.tick(MAIN_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, str(controller.id))})
        is None
    )
    for zone in zones:
        device = device_registry.async_get_device(identifiers={(DOMAIN, str(zone.id))})
        assert device is None
    all_devices = dr.async_entries_for_config_entry(
        device_registry, mock_added_config_entry.entry_id
    )
    assert len(all_devices) == 0
