"""Tests for the MyNeomitis climate component."""

from unittest.mock import AsyncMock, call

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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

    entity_registry.async_update_entity("climate.climate_device", aliases=set())

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


async def test_set_preset_mode_unknown_no_api_call(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Unknown preset mode should not call the API and should keep current mode."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: entity_id, "preset_mode": "not-a-mode"},
            blocking=True,
        )

    mock_pyaxenco_client.set_device_mode.assert_not_awaited()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "comfort"


async def test_set_preset_mode_sub_device_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Sub-device preset mode timeout should raise HomeAssistantError."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_SUB_DEVICE]
    mock_pyaxenco_client.set_sub_device_mode.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_sub_device"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {ATTR_ENTITY_ID: entity_id, "preset_mode": "eco"},
            blocking=True,
        )

    mock_pyaxenco_client.set_sub_device_mode.assert_awaited_with("gw-1", "rfid-1", 2)


async def test_set_temperature_sub_device_missing_parents(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Missing parents/rfid for sub-device should fail temperature set without API call."""
    bad_sub = {**CLIMATE_SUB_DEVICE, "parents": {}, "rfid": None}
    mock_pyaxenco_client.get_devices.return_value = [bad_sub]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_sub_device"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21.0},
            blocking=True,
        )

    mock_pyaxenco_client.set_sub_device_mode.assert_not_awaited()
    mock_pyaxenco_client.set_sub_device_temperature.assert_not_awaited()


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

    mock_pyaxenco_client.set_sub_device_mode.assert_awaited_with("gw-1", "rfid-1", 8)
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
    assert state.attributes.get("hvac_modes") == [HVACMode.COOL, HVACMode.OFF]


async def test_skip_device_without_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Devices without _id are skipped during setup."""
    mock_pyaxenco_client.get_devices.return_value = [{"model": "EV30", "name": "NoID"}]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not any(e.domain == "climate" for e in entries)


async def test_skip_unknown_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unknown models are skipped during setup."""
    mock_pyaxenco_client.get_devices.return_value = [
        {
            "_id": "x",
            "name": "Unknown",
            "model": "UNKNOWN",
            "state": {},
            "connected": True,
        }
    ]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not any(e.domain == "climate" for e in entries)


async def test_handle_ws_update_empty_returns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Empty websocket payload should not change climate values."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    before = hass.states.get(entity_id)
    assert before is not None

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]
    callback({})
    await hass.async_block_till_done()

    after = hass.states.get(entity_id)
    assert after is not None
    assert after.state == before.state
    assert (
        after.attributes["current_temperature"]
        == before.attributes["current_temperature"]
    )


async def test_override_temp_update_from_websocket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """OverrideTemp websocket update should update target temperature."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]
    callback({"overrideTemp": 25})
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate_device")
    assert state is not None
    assert state.attributes["temperature"] == 25


async def test_target_temp_update_from_websocket_sub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """TargetTemp websocket update should update sub-device target temperature."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_SUB_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]
    callback({"targetTemp": 22})
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate_sub_device")
    assert state is not None
    assert state.attributes["temperature"] == 22


async def test_targetmode_standby_sets_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """TargetMode of 4 (standby) via websocket should set HVAC mode to OFF."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]
    callback({"targetMode": 4})
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate_device")
    assert state is not None
    assert state.state == "off"


async def test_changeover_updates_hvac_when_not_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """ChangeOverUser websocket update should switch active NTD mode to cool."""
    ntd_heat = {
        **CLIMATE_NTD_COOL,
        "_id": "climate_ntd_heat",
        "name": "Climate NTD Heat",
        "state": {**CLIMATE_NTD_COOL["state"], "changeOverUser": 0},
    }
    mock_pyaxenco_client.get_devices.return_value = [ntd_heat]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate_ntd_heat")
    assert state is not None
    assert state.state == "heat"

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]
    callback({"changeOverUser": 1})
    await hass.async_block_till_done()

    state = hass.states.get("climate.climate_ntd_heat")
    assert state is not None
    assert state.state == "cool"


async def test_set_preset_mode_standby_sets_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Setting preset mode to standby sets HVAC mode to off."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: entity_id, "preset_mode": "standby"},
        blocking=True,
    )

    mock_pyaxenco_client.set_device_mode.assert_awaited_with("climate1", 4)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_set_preset_mode_when_hvac_off_ntd_sets_cool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Setting a preset on an OFF NTD entity should bring it back to cool."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_NTD_COOL]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_ntd"
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: entity_id, "preset_mode": "eco"},
        blocking=True,
    )

    mock_pyaxenco_client.set_sub_device_mode.assert_has_awaits(
        [call("gw-ntd", "rfid-ntd", 4), call("gw-ntd", "rfid-ntd", 2)]
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "cool"


async def test_set_hvac_mode_restore_fallback_uses_first_non_standby(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Restoring from standby should use the first non-standby preset."""
    standby_device = {
        **CLIMATE_DEVICE,
        "_id": "climate_standby",
        "name": "Climate Standby",
        "state": {**CLIMATE_DEVICE["state"], "targetMode": 4},
    }
    mock_pyaxenco_client.get_devices.return_value = [standby_device]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_standby"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    mock_pyaxenco_client.set_device_mode.assert_awaited_with("climate_standby", 8)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "setpoint"
    assert state.state == "heat"


async def test_set_hvac_mode_off_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Setting HVAC mode to off that fails at API should raise HomeAssistantError."""
    mock_pyaxenco_client.get_devices.return_value = [CLIMATE_DEVICE]
    mock_pyaxenco_client.set_device_mode.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "climate.climate_device"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": "off"},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "comfort"
