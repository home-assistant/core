"""Test for Sensibo integration setup."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysensibo.model import SensiboData
import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.util import NoUsernameError
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_load_unload_entry(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test setup and unload config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="firstnamelastname",
        version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="someother",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == "firstnamelastname"


async def test_migrate_entry_fails(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test migrate entry fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="someother",
        version=1,
    )
    entry.add_to_hass(hass)

    mock_client.async_get_me.side_effect = NoUsernameError("No username returned")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert entry.unique_id == "someother"


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    load_int: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    entity = entity_registry.entities["climate.hallway"]

    device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, load_int.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=load_int.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    response = await client.remove_device(dead_device_entry.id, load_int.entry_id)
    assert response["success"]


@pytest.mark.parametrize(
    ("entity_id", "device_ids"),
    [
        # Device is ABC999111
        ("climate.hallway", ["ABC999111"]),
        ("binary_sensor.hallway_filter_clean_required", ["ABC999111"]),
        ("number.hallway_temperature_calibration", ["ABC999111"]),
        ("sensor.hallway_filter_last_reset", ["ABC999111"]),
        ("update.hallway_firmware", ["ABC999111"]),
        # Device is AABBCC belonging to device ABC999111
        ("binary_sensor.hallway_motion_sensor_motion", ["ABC999111", "AABBCC"]),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_automatic_device_addition_and_removal(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any], dict[str, Any]],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    device_ids: list[str],
) -> None:
    """Test for automatic device addition and removal."""

    state = hass.states.get(entity_id)
    assert state
    assert entity_registry.async_get(entity_id)
    for device_id in device_ids:
        assert device_registry.async_get_device(identifiers={(DOMAIN, device_id)})

    # Remove one of the devices
    new_device_list = [
        device for device in get_data[2]["result"] if device["id"] != device_ids[0]
    ]
    mock_client.async_get_devices.return_value = {
        "status": "success",
        "result": new_device_list,
    }
    new_data = {k: v for k, v in get_data[0].parsed.items() if k != device_ids[0]}
    new_raw = mock_client.async_get_devices.return_value["result"]
    mock_client.async_get_devices_data.return_value = SensiboData(new_raw, new_data)

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert not state
    assert not entity_registry.async_get(entity_id)
    for device_id in device_ids:
        assert not device_registry.async_get_device(identifiers={(DOMAIN, device_id)})

    # Add the device back
    mock_client.async_get_devices.return_value = get_data[2]
    mock_client.async_get_devices_data.return_value = get_data[0]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert entity_registry.async_get(entity_id)
    for device_id in device_ids:
        assert device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
