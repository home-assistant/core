"""Tests for the MyNeomitis climate component."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

CLIMATE_DEVICE = {
    "_id": "climate1",
    "name": "Climate Device",
    "model": "EV30",
    "state": {
        "currentTemp": 21.5,
        "overrideTemp": 22.0,
        "targetMode": 1,
        "comfLimitMin": 7,
        "comfLimitMax": 30,
        "connected": True,
    },
    "connected": True,
    "program": {"data": {}},
}

CLIMATE_SUB_DEVICE = {
    "_id": "climate_sub1",
    "name": "Climate Sub Device",
    "model": "NTD",
    "state": {
        "currentTemp": 19.0,
        "targetTemp": 20.0,
        "targetMode": 1,
        "comfLimitMin": 7,
        "comfLimitMax": 30,
        "connected": True,
    },
    "connected": True,
    "parents": {"gateway": "gw-1"},
    "rfid": "rfid-1",
    "program": {"data": {}},
}

CLIMATE_NTD_COOL = {
    "_id": "climate_ntd1",
    "name": "Climate NTD",
    "model": "NTD",
    "state": {
        "currentTemp": 20.0,
        "targetTemp": 21.0,
        "targetMode": 1,
        "comfLimitMin": 7,
        "comfLimitMax": 30,
        "changeOverUser": 1,
        "connected": True,
    },
    "connected": True,
    "parents": {"gateway": "gw-ntd"},
    "rfid": "rfid-ntd",
    "program": {"data": {}},
}


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate entity is created for supported device."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test setting target temperature."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "climate.climate_device"

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )
    mock_pyaxenco_client.set_device_mode.assert_awaited_with("climate1", 8)
    mock_pyaxenco_client.set_device_temperature.assert_awaited_with("climate1", 23.5)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["temperature"] == 23.5


async def test_set_preset_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test setting preset mode."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "climate.climate_device"
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: entity_id, "preset_mode": "eco"},
        blocking=True,
    )
    mock_pyaxenco_client.set_device_mode.assert_awaited_with("climate1", 2)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "eco"


async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test setting hvac mode."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = "climate.climate_device"
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": "off"},
        blocking=True,
    )
    mock_pyaxenco_client.set_device_mode.assert_awaited_with("climate1", 4)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_websocket_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that entity updates when source data changes via WebSocket."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "heat"

    mock_pyaxenco_client.register_listener.assert_called_once()
    callback = mock_pyaxenco_client.register_listener.call_args[0][1]

    callback({"currentTemp": 19.0})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["current_temperature"] == 19.0

    callback({"targetMode": 2})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "eco"


async def test_device_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that entity becomes unavailable when device connection is lost."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "heat"

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]

    callback({"connected": False})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


async def test_set_temperature_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """API errors when setting temperature should be handled gracefully."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_pyaxenco_client.set_device_temperature.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.5},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["temperature"] == 22.0


async def test_set_preset_mode_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """API errors when setting preset mode should be handled gracefully."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_pyaxenco_client.set_device_mode.side_effect = ConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: entity_id, "preset_mode": "eco"},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "comfort"


async def test_set_temperature_sub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test setting temperature for a sub-device uses sub-device API."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_SUB_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_sub_device"
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )

    mock_pyaxenco_client.set_sub_device_mode.assert_awaited()
    mock_pyaxenco_client.set_sub_device_temperature.assert_awaited_with(
        "gw-1", "rfid-1", 21.0
    )


async def test_set_preset_mode_sub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test setting preset mode for a sub-device uses sub-device API."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_SUB_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_sub_device"
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: entity_id, "preset_mode": "eco"},
        blocking=True,
    )

    mock_pyaxenco_client.set_sub_device_mode.assert_awaited_with("gw-1", "rfid-1", 2)


async def test_ntd_changeover_sets_cool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """NTD devices with changeOverUser==1 should expose COOL and OFF modes and start in COOL."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_NTD_COOL]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_ntd"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "cool"
    assert state.attributes.get("hvac_modes") == ["cool", "off"]
