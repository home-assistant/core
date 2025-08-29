"""Tests for the MyNeoSelect component."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.components.myneomitis.select import MyNeoSelect, async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


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

    select = MyNeoSelect(mock_api, device, [device])

    assert select.name == "MyNeo Relais Salon"
    assert select.options == ["on", "off", "auto"]
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

    select = MyNeoSelect(mock_api, device, [device])

    assert select.name == "MyNeo Thermostat Salon"
    assert "comfort" in select.options
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

    select = MyNeoSelect(mock_api, device, [device])

    assert select.name == "MyNeo UFH Salon"
    assert select.options == ["cooling", "heating"]

    assert select.current_option == "heating"
    select.current_option = "cooling"
    assert select.current_option == "cooling"


async def test_dynamic_select_added_on_link_event(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that a select entity is added dynamically on WebSocket link event."""
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        entry_id="select-link",
        domain=DOMAIN,
        title="MyNeomitis",
        data={"email": "test@test.com", "password": "secret"},
        options={},
        source="user",
        unique_id="uid",
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api": fake_api, "devices": []}

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
    assert len(added) == 1
    entity = added[0]
    assert isinstance(entity, MyNeoSelect)
    assert entity.name == "MyNeo Relais Salon"
    assert entity.unique_id == "myneo_ews1"


async def test_dynamic_select_removed_on_unlink_event(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that a select entity is removed dynamically on WebSocket unlink event."""

    class DummySelect(MyNeoSelect):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.async_remove_called = False

        async def async_remove(self) -> None:
            self.async_remove_called = True

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        entry_id="select-unlink",
        domain=DOMAIN,
        title="MyNeomitis",
        data={"email": "test@test.com", "password": "secret"},
        options={},
        source="user",
        unique_id="uid",
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

    device = {
        "_id": "ews2",
        "name": "Relais Cuisine",
        "model": "EWS",
        "state": {"targetMode": 1, "relayMode": True, "connected": True},
        "connected": True,
        "program": {"data": {}},
    }

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": fake_api,
        "devices": [device],
    }

    added = []

    def fake_add(entities):
        added.extend(entities)

    with patch("myneomitis.select.MyNeoSelect", DummySelect):
        await async_setup_entry(hass, entry, fake_add)

    assert len(added) == 1
    entity = added[0]
    assert isinstance(entity, DummySelect)
    assert not entity.async_remove_called

    callbacks["removal"]("ews2")
    await hass.async_block_till_done()

    assert entity.async_remove_called


def test_extra_state_attributes_with_program() -> None:
    """Test extra state attributes for MyNeoSelect with a program."""
    device = {
        "_id": "dev1",
        "name": "Test",
        "model": "EWS",
        "state": {"targetMode": 2, "relayMode": 1},
        "connected": True,
        "program": {
            "data": {
                "MON": [{"start": "06:00", "mode": 1}],
                "TUE": [],
                "WED": [],
                "THU": [],
                "FRI": [],
                "SAT": [],
                "SUN": [],
            }
        },
    }

    mock_api = Mock()
    mock_api.sio.connected = True
    select = MyNeoSelect(mock_api, device, [device])
    attrs = select.extra_state_attributes

    assert attrs["ws_status"] == "connected"
    assert attrs["is_connected"] == "True"
    assert "planning_monday" in attrs


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
    select = MyNeoSelect(mock_api, device, [device])

    with patch("myneomitis.select._LOGGER.warning") as mock_warn:
        await select.async_select_option("invalid_mode")
        mock_warn.assert_called_once()
