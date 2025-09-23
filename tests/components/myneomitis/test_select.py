"""Tests for the MyNeoSelect component."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.components.myneomitis.select import MyNeoSelect, async_setup_entry
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

    select = MyNeoSelect(mock_api, device, [device])

    assert select.name == "MyNeo Thermostat Salon"
    assert "comfort" in select.options
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

    select = MyNeoSelect(mock_api, device, [device])

    assert select.name == "MyNeo UFH Salon"
    assert select.options == ["cooling", "heating"]

    assert select.current_option == "heating"
    select.current_option = "cooling"
    assert select.current_option == "cooling"


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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

    with patch("homeassistant.components.myneomitis.select.MyNeoSelect", DummySelect):
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
    select = MyNeoSelect(mock_api, device, [device])

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

    select = MyNeoSelect(mock_api, device, [device])
    ws_state = {"changeOverUser": 1, "connected": True, "name": "UFH Salon"}
    with patch.object(select, "async_write_ha_state") as mock_write:
        select.handle_ws_update(ws_state)
        mock_write.assert_called()
        assert select.current_option in ["cooling", "heating"]
        assert select.name == "UFH Salon"
        assert select.available is True


@pytest.mark.asyncio
async def test_extra_state_attributes_without_sio(hass: HomeAssistant) -> None:
    """Test extra_state_attributes when sio is missing."""
    device = {
        "_id": "dev_sio",
        "name": "Test Device",
        "model": "EWS",
        "state": {"targetMode": 1, "relayMode": 0},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = Mock()
    mock_api.sio = Mock()
    mock_api.sio.connected = False

    select = MyNeoSelect(mock_api, device, [device])
    attrs = select.extra_state_attributes
    assert attrs["ws_status"] == "disconnected"
    assert attrs["is_connected"] == "True"


@pytest.mark.asyncio
async def test_set_api_device_mode_sub_devices(hass: HomeAssistant) -> None:
    """Test set_api_device_mode for UFH sub-devices and other sub-devices."""
    devices = [
        {
            "_id": "ufh1",
            "name": "UFH Room",
            "model": "UFH",
            "rfid": "rfh1",
            "state": {"changeOverUser": 0},
            "connected": True,
            "parents": "gw1,parent1",
            "program": {"data": {}},
        },
        {
            "_id": "sub1",
            "name": "Sub Device",
            "model": "SUB",
            "rfid": "rfh2",
            "state": {},
            "connected": True,
            "parents": "gw2,parent2",
            "program": {"data": {}},
        },
    ]

    mock_api = Mock()
    mock_api.sio = Mock()
    mock_api.sio.connected = True
    mock_api.set_sub_device_mode_ufh = AsyncMock()
    mock_api.set_sub_device_mode = AsyncMock()
    mock_api.set_device_mode = AsyncMock()

    ufh_select = MyNeoSelect(mock_api, devices[0], devices)
    sub_select = MyNeoSelect(mock_api, devices[1], devices)

    sub_select._preset_mode_map = {"auto": 1}
    sub_select._is_sub_device = True  # for test purposes

    await ufh_select.set_api_device_mode("heating")
    mock_api.set_sub_device_mode_ufh.assert_awaited_once_with(
        "gw1", "rfh1", ufh_select._preset_mode_map["heating"]
    )

    await sub_select.set_api_device_mode("auto")
    mock_api.set_sub_device_mode.assert_awaited_once_with("gw2", "rfh2", 1)


def test_icon_for_all_options() -> None:
    """Test icon property for all special options."""
    options_map = {
        "off": "mdi:toggle-switch-off-outline",
        "standby": "mdi:toggle-switch-off-outline",
        "eco": "mdi:leaf",
        "eco-1": "mdi:leaf",
        "eco-2": "mdi:leaf",
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
        select = MyNeoSelect(mock_api, device, [device])
        select._attr_current_option = opt
        assert select.icon == icon


@pytest.mark.asyncio
async def test_async_setup_entry_add_and_remove_entities(hass: HomeAssistant) -> None:
    """Test async_setup_entry with dynamic add and removal of entities."""

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        entry_id="entry1",
        domain="myneomitis",
        title="MyNeo",
        data={},
        options={},
        source="user",
        unique_id="uid1",
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
    fake_api.register_listener = Mock()
    fake_api.register_discovery_callback = register_discovery_callback
    fake_api.register_removal_callback = register_removal_callback

    device = {
        "_id": "dev_add",
        "name": "Add Device",
        "model": "EWS",
        "state": {"targetMode": 1, "relayMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    hass.data.setdefault("myneomitis", {})[entry.entry_id] = {
        "api": fake_api,
        "devices": [device],
    }

    added = []

    def fake_add(entities):
        added.extend(entities)

    await async_setup_entry(hass, entry, fake_add)

    # Test dynamic addition of a new device
    new_device = {
        "_id": "dev_new",
        "name": "New Device",
        "model": "EWS",
        "state": {"targetMode": 1, "relayMode": 1},
        "connected": True,
        "program": {"data": {}},
    }
    callbacks["discovery"](new_device)
    assert len(added) == 2

    # Test removal of a device
    entity_to_remove = added[0]
    entity_to_remove.async_remove = AsyncMock()
    callbacks["removal"](device["_id"])
    await hass.async_block_till_done()
    entity_to_remove.async_remove.assert_awaited_once()


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

    select = MyNeoSelect(mock_api, device, [device])
    select._preset_mode_map = {"comfort": 1}  # define preset map
    select._is_sub_device = False

    await select.set_api_device_mode("comfort")
    mock_api.set_device_mode.assert_awaited_once_with("dev_normal", 1)


class ApiWithoutSio:
    """Fake API with no real sio attribute."""

    class FakeSio:
        """FakeSio for test."""

        connected = False

    def __init__(self) -> None:
        """Init the FakeSio."""
        self.sio = ApiWithoutSio.FakeSio()

    def register_listener(self, device_id, callback) -> None:
        """Fake empty register_listener."""


@pytest.mark.asyncio
async def test_extra_state_attributes_no_sio_attr(hass: HomeAssistant) -> None:
    """Test extra_state_attributes when API has no sio attribute (simulate disconnected)."""
    device = {
        "_id": "dev_no_sio",
        "name": "No SIO Device",
        "model": "EWS",
        "state": {"targetMode": 1},
        "connected": True,
        "program": {"data": {}},
    }

    mock_api = ApiWithoutSio()
    select = MyNeoSelect(mock_api, device, [device])

    attrs = select.extra_state_attributes
    assert attrs["ws_status"] == "disconnected"
    assert attrs["is_connected"] == "True"
