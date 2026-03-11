"""Tests for the MyNeomitis select component."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

RELAIS_DEVICE = {
    "_id": "relais1",
    "name": "Relais Device",
    "model": "EWS",
    "state": {"relayMode": 1, "targetMode": 2},
    "connected": True,
    "program": {"data": {}},
}

PILOTE_DEVICE = {
    "_id": "pilote1",
    "name": "Pilote Device",
    "model": "EWS",
    "state": {"targetMode": 1},
    "connected": True,
    "program": {"data": {}},
}

UFH_DEVICE = {
    "_id": "ufh1",
    "name": "UFH Device",
    "model": "UFH",
    "state": {"changeOverUser": 0},
    "connected": True,
    "program": {"data": {}},
}


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all select entities are created for supported devices."""
    mock_pyaxenco_client.get_devices.return_value = [
        RELAIS_DEVICE,
        PILOTE_DEVICE,
        UFH_DEVICE,
        {
            "_id": "unsupported",
            "name": "Unsupported Device",
            "model": "UNKNOWN",
            "state": {},
            "connected": True,
            "program": {"data": {}},
        },
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that selecting an option propagates to the library correctly."""
    mock_pyaxenco_client.get_devices.return_value = [RELAIS_DEVICE]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.relais_device", "option": "on"},
        blocking=True,
    )

    mock_pyaxenco_client.set_device_mode.assert_awaited_once_with("relais1", 1)

    state = hass.states.get("select.relais_device")
    assert state is not None
    assert state.state == "on"


async def test_websocket_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that entity updates when source data changes via WebSocket."""
    mock_pyaxenco_client.get_devices.return_value = [RELAIS_DEVICE]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.relais_device")
    assert state is not None
    assert state.state == "off"

    mock_pyaxenco_client.register_listener.assert_called_once()
    callback = mock_pyaxenco_client.register_listener.call_args[0][1]

    callback({"targetMode": 1})
    await hass.async_block_till_done()

    state = hass.states.get("select.relais_device")
    assert state is not None
    assert state.state == "on"


async def test_device_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyaxenco_client: AsyncMock,
) -> None:
    """Test that entity becomes unavailable when device connection is lost."""
    mock_pyaxenco_client.get_devices.return_value = [RELAIS_DEVICE]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.relais_device")
    assert state is not None
    assert state.state == "off"

    callback = mock_pyaxenco_client.register_listener.call_args[0][1]

    callback({"connected": False})
    await hass.async_block_till_done()

    state = hass.states.get("select.relais_device")
    assert state is not None
    assert state.state == "unavailable"
