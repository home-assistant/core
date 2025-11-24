"""Tests for the MyNeoSelect component."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.myneomitis import MyNeomitisRuntimeData
from homeassistant.components.myneomitis.select import (
    SELECT_TYPES,
    MyNeoSelect,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_myneo_relay_select_basic_behavior(hass: HomeAssistant) -> None:
    """Test initialization and behavior of MyNeoSelect with relais mode."""
    device = {
        "_id": "dev1",
        "name": "Relais Salon",
        "model": "EWS",
        "state": {"relayMode": 1, "targetMode": 2},
        "connected": True,
        "program": {
            "data": dict.fromkeys(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"), ())
        },
    }

    mock_api = Mock()
    mock_api.sio.connected = True
    mock_api.set_device_mode = AsyncMock()

    description = SELECT_TYPES["relais"]
    select = MyNeoSelect(mock_api, device, [device], description)

    assert select.name == "MyNeo Relais Salon"
    assert select.entity_description.options == ["on", "off", "auto"]
    assert select.current_option == "off"
    assert select.icon == "mdi:toggle-switch-off-outline"

    select.hass = hass
    select.entity_id = "select.myneo_relais_salon"

    await select.async_added_to_hass()

    with patch.object(select, "async_write_ha_state"):
        await select.async_select_option("on")

    assert select.current_option == "on"
    mock_api.set_device_mode.assert_called_once_with("dev1", 1)

    ws_state = {"targetMode": 2}
    with patch.object(select, "async_write_ha_state"):
        select.handle_ws_update(ws_state)

    assert select.current_option == "off"


@pytest.mark.asyncio
async def test_myneo_select_preset_modes(hass: HomeAssistant) -> None:
    """Test initialization and behavior of MyNeoSelect with preset modes."""
    device = {
        "_id": "dev2",
        "name": "Thermostat Salon",
        "model": "EWS",
        "state": {"targetMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.sio.connected = True
    mock_api.set_device_mode = AsyncMock()

    description = SELECT_TYPES["pilote"]
    select = MyNeoSelect(mock_api, device, [device], description)

    assert select.name == "MyNeo Thermostat Salon"
    assert "comfort" in select.entity_description.options
    assert select.current_option == "comfort"

    select.current_option = "eco"
    assert select.current_option == "eco"


@pytest.mark.asyncio
async def test_myneo_select_ufh_modes(hass: HomeAssistant) -> None:
    """Test initialization and behavior of MyNeoSelect with UFH modes."""
    device = {
        "_id": "dev3",
        "name": "UFH Salon",
        "model": "UFH",
        "state": {"changeOverUser": 0},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.sio.connected = True
    mock_api.set_device_mode = AsyncMock()

    description = SELECT_TYPES["UFH"]
    select = MyNeoSelect(mock_api, device, [device], description)

    assert select.name == "MyNeo UFH Salon"
    assert select.entity_description.options == ["cooling", "heating"]
    assert select.current_option == "heating"

    select.current_option = "cooling"
    assert select.current_option == "cooling"


@pytest.mark.asyncio
async def test_select_option_with_invalid_option(hass: HomeAssistant) -> None:
    """Test that selecting an invalid option logs a warning and does not change the state."""
    device = {
        "_id": "dev_invalid",
        "name": "Invalid Device",
        "model": "EWS",
        "state": {"relayMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.sio.connected = True
    description = SELECT_TYPES["relais"]
    select = MyNeoSelect(mock_api, device, [device], description)

    with patch(
        "homeassistant.components.myneomitis.select._LOGGER.warning"
    ) as mock_warn:
        await select.async_select_option("invalid_mode")
        mock_warn.assert_called_once()


@pytest.mark.asyncio
async def test_ufh_handle_ws_update_and_sub_device(hass: HomeAssistant) -> None:
    """Test UFH device websocket updates and sub-device mode setting."""
    device = {
        "_id": "ufh1",
        "name": "UFH Chamber",
        "model": "UFH",
        "state": {"changeOverUser": 0},
        "connected": False,
        "program": {"data": {}},
        "rfid": "rfid123",
        "parents": "gw1,parent1",
    }

    mock_api = Mock()
    mock_api.sio = Mock()
    mock_api.sio.connected = False
    mock_api.set_sub_device_mode_ufh = AsyncMock()
    mock_api.set_sub_device_mode = AsyncMock()
    mock_api.set_device_mode = AsyncMock()
    mock_api.register_listener = Mock()

    description = SELECT_TYPES["UFH"]
    select = MyNeoSelect(mock_api, device, [device], description)

    ws_state = {"changeOverUser": 1, "connected": True, "name": "UFH Salon"}
    with patch.object(select, "async_write_ha_state") as mock_write:
        select.handle_ws_update(ws_state)
        mock_write.assert_called()
        assert select.current_option in ["cooling", "heating"]
        assert select.name == "UFH Salon"
        assert select.available is True


@pytest.mark.asyncio
async def test_icon_for_all_options(hass: HomeAssistant) -> None:
    """Test icon property for all special options."""
    options_map = {
        "off": "mdi:toggle-switch-off-outline",
        "standby": "mdi:toggle-switch-off-outline",
        "eco": "mdi:leaf",
        "eco_1": "mdi:leaf",
        "eco_2": "mdi:leaf",
        "comfort": "mdi:fire",
        "heating": "mdi:fire",
        "antifrost": "mdi:snowflake",
        "cooling": "mdi:snowflake",
        "boost": "mdi:rocket-launch",
        "auto": "mdi:refresh-auto",
        "unknown": "mdi:toggle-switch",
    }

    for opt, icon in options_map.items():
        device = {
            "_id": "dev_icon",
            "name": "Icon Test",
            "model": "EWS",
            "state": {"targetMode": 0, "relayMode": 1},
            "connected": True,
            "program": {"data": {}},
        }
        mock_api = Mock()
        mock_api.sio.connected = True
        description = SELECT_TYPES["relais"]
        select = MyNeoSelect(mock_api, device, [device], description)
        select._attr_current_option = opt
        assert select.icon == icon


@pytest.mark.asyncio
async def test_normal_device_set_api_device_mode(hass: HomeAssistant) -> None:
    """Test set_api_device_mode for a normal device (not sub-device)."""
    device = {
        "_id": "dev_normal",
        "name": "Normal Device",
        "model": "EWS",
        "state": {"targetMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.sio = Mock()
    mock_api.sio.connected = True
    mock_api.set_device_mode = AsyncMock()

    description = SELECT_TYPES["pilote"]
    select = MyNeoSelect(mock_api, device, [device], description)
    select._is_sub_device = False

    await select.set_api_device_mode("comfort")
    mock_api.set_device_mode.assert_awaited_once_with("dev_normal", 1)


@pytest.mark.asyncio
async def test_dynamic_entity_discovery(hass: HomeAssistant) -> None:
    """Test that a select entity is added dynamically on WebSocket discovery event."""
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        entry_id="select-link",
        domain="myneomitis",
        title="MyNeomitis",
        data={"email": "test@test.com", "password": "secret"},
        options={},
        source="user",
        unique_id="uid",
        discovery_keys=[],
        subentries_data={},
    )

    callbacks = {}

    def register_discovery_callback(cb):
        callbacks["discovery"] = cb

    def register_removal_callback(cb):
        callbacks["removal"] = cb

    fake_api = Mock()
    fake_api.sio.connected = True
    fake_api.register_listener = lambda *_: None
    fake_api.register_discovery_callback = register_discovery_callback
    fake_api.register_removal_callback = register_removal_callback

    entry.runtime_data = MyNeomitisRuntimeData(api=fake_api, devices=[])

    added = []

    def fake_add(entities):
        added.extend(entities)

    await async_setup_entry(hass, entry, fake_add)

    linked_device = {
        "_id": "ews1",
        "name": "Relais Salon",
        "model": "EWS",
        "state": {"targetMode": 1, "relayMode": True, "connected": True},
        "connected": True,
        "program": {"data": {}},
    }

    callbacks["discovery"](linked_device)
    await hass.async_block_till_done()

    assert len(added) == 1
    entity = added[0]
    assert isinstance(entity, MyNeoSelect)
    assert entity.name == "MyNeo Relais Salon"
    assert entity.unique_id == "myneo_ews1"
