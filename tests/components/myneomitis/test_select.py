"""Tests for the MyNeoSelect component."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.myneomitis.select import SELECT_TYPES, MyNeoSelect
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


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
    select = MyNeoSelect(mock_api, device, description)

    assert select.has_entity_name is True
    assert select._attr_device_info["name"] == "Relais Salon"
    assert select.entity_description.options == ["on", "off", "auto"]
    assert select.current_option == "off"

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
    select = MyNeoSelect(mock_api, device, description)

    assert select.has_entity_name is True
    assert select._attr_device_info["name"] == "Thermostat Salon"
    assert "comfort" in select.entity_description.options
    assert select.current_option == "comfort"

    select.current_option = "eco"
    assert select.current_option == "eco"


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
    select = MyNeoSelect(mock_api, device, description)

    assert select.has_entity_name is True
    assert select._attr_device_info["name"] == "UFH Salon"
    assert select.entity_description.options == ["heating", "cooling"]
    assert select.current_option == "heating"

    select.current_option = "cooling"
    assert select.current_option == "cooling"


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
    select = MyNeoSelect(mock_api, device, description)

    with patch(
        "homeassistant.components.myneomitis.select._LOGGER.warning"
    ) as mock_warn:
        await select.async_select_option("invalid_mode")
        mock_warn.assert_called_once()


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
    select = MyNeoSelect(mock_api, device, description)

    ws_state = {"changeOverUser": 1, "connected": True}
    with patch.object(select, "async_write_ha_state") as mock_write:
        select.handle_ws_update(ws_state)
        mock_write.assert_called()
        assert select.current_option in ["cooling", "heating"]
        assert select.available is True


async def test_setup_entry_filters_unsupported_devices(hass: HomeAssistant) -> None:
    """Test that async_setup_entry filters out unsupported device models."""
    devices = [
        {
            "_id": "supported1",
            "name": "Supported EWS",
            "model": "EWS",
            "state": {"targetMode": 1},
            "connected": True,
            "program": {"data": {}},
        },
        {
            "_id": "unsupported",
            "name": "Unsupported Device",
            "model": "UNKNOWN",
            "state": {},
            "connected": True,
            "program": {"data": {}},
        },
    ]

    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=devices)
        api.disconnect_websocket = AsyncMock()

        entry = MockConfigEntry(
            domain="myneomitis", data={"email": "test@test.com", "password": "secret"}
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert len(entries) == 1
    assert entries[0].unique_id == "supported1"


async def test_handle_ws_update_empty_state(hass: HomeAssistant) -> None:
    """Test handle_ws_update with empty state does nothing."""
    device = {
        "_id": "dev_ws",
        "name": "WS Test",
        "model": "EWS",
        "state": {"targetMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.register_listener = Mock()
    description = SELECT_TYPES["pilote"]
    select = MyNeoSelect(mock_api, device, description)

    initial_option = select.current_option

    with patch.object(select, "async_write_ha_state") as mock_write:
        select.handle_ws_update({})

        mock_write.assert_not_called()

    assert select.current_option == initial_option


async def test_handle_ws_update_with_program_update(hass: HomeAssistant) -> None:
    """Test handle_ws_update updates program data."""
    device = {
        "_id": "dev_prog",
        "name": "Program Test",
        "model": "EWS",
        "state": {"targetMode": 1},
        "connected": True,
        "program": {"data": {"MON": []}},
    }

    mock_api = Mock()
    mock_api.register_listener = Mock()
    description = SELECT_TYPES["pilote"]
    select = MyNeoSelect(mock_api, device, description)

    new_program = {"TUE": [1, 2, 3]}
    ws_state = {"program": {"data": new_program}}

    with patch.object(select, "async_write_ha_state") as mock_write:
        select.handle_ws_update(ws_state)
        mock_write.assert_called_once()

    assert select._program["TUE"] == [1, 2, 3]


async def test_create_entity_with_pilote_device(hass: HomeAssistant) -> None:
    """Test that EWS device without relayMode creates pilote entity."""
    device = {
        "_id": "pilote1",
        "name": "Pilote Device",
        "model": "EWS",
        "state": {"targetMode": 1},  # No relayMode
        "connected": True,
        "program": {"data": {}},
    }

    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[device])
        api.disconnect_websocket = AsyncMock()

        entry = MockConfigEntry(
            domain="myneomitis", data={"email": "test@test.com", "password": "secret"}
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert "options" in state.attributes
    assert "comfort" in state.attributes[
        "options"
    ] or "comfort" in state.attributes.get("options", [])


async def test_create_entity_with_ufh_device(hass: HomeAssistant) -> None:
    """Test that UFH device creates UFH entity."""
    device = {
        "_id": "ufh1",
        "name": "UFH Device",
        "model": "UFH",
        "state": {"changeOverUser": 0},
        "connected": True,
        "program": {"data": {}},
    }

    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[device])
        api.disconnect_websocket = AsyncMock()

        entry = MockConfigEntry(
            domain="myneomitis", data={"email": "test@test.com", "password": "secret"}
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert "options" in state.attributes
    assert "heating" in state.attributes[
        "options"
    ] or "heating" in state.attributes.get("options", [])


async def test_create_entity_with_relais_device(hass: HomeAssistant) -> None:
    """Test that EWS device with relayMode creates relais entity."""
    device = {
        "_id": "relais1",
        "name": "Relais Device",
        "model": "EWS",
        "state": {"relayMode": 1, "targetMode": 2},  # Has relayMode
        "connected": True,
        "program": {"data": {}},
    }

    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[device])
        api.disconnect_websocket = AsyncMock()

        entry = MockConfigEntry(
            domain="myneomitis", data={"email": "test@test.com", "password": "secret"}
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert "options" in state.attributes
    assert any(opt in state.attributes["options"] for opt in ("on", "off", "auto"))
