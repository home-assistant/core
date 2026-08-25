"""Tests for the Haus-Bus cover platform."""

from unittest.mock import MagicMock

from pyhausbus import HausBusUtils
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Rollladen import Rollladen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvClosed import EvClosed
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvOpen import EvOpen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvStart import EvStart
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.Status import Status
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.params.EDirection import (
    EDirection,
)

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry

DEVICE_ID = 100
INSTANCE_ID = 1
OBJECT_ID = HausBusUtils.getObjectId(DEVICE_ID, Rollladen.CLASS_ID, INSTANCE_ID)
UNIQUE_ID = f"{DEVICE_ID}-rollladen-{INSTANCE_ID}"
UPDATE_SIGNAL = f"hausbus_update_{OBJECT_ID}"


def _make_channel() -> MagicMock:
    """Create a mock Rollladen channel with a real, decodable object id."""
    channel = MagicMock(spec=Rollladen)
    channel.getObjectId.return_value = OBJECT_ID
    channel.getName.return_value = "Wohnzimmer"
    return channel


def _make_module_id() -> MagicMock:
    """Create a mock ModuleId with the fields newDeviceDetected reads."""
    module_id = MagicMock(spec=ModuleId)
    module_id.getFirmwareId.return_value = EFirmwareId.ESP32
    module_id.getMajorRelease.return_value = 1
    module_id.getMinorRelease.return_value = 0
    module_id.getName.return_value = "ESP32"
    return module_id


async def _setup_cover(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> tuple[str, MagicMock]:
    """Set up a config entry and simulate one discovered Rollladen channel.

    Regression guard: _handle_channel_added must stay marked @callback.
    Undecorated, the dispatcher runs it on an executor thread, where
    async_add_entities() breaks.
    """
    mock_home_server.is_any_device_found.return_value = True
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    gateway = entry.runtime_data
    channel = _make_channel()

    await hass.async_add_executor_job(
        gateway.newDeviceDetected,
        DEVICE_ID,
        "ESP32 Controller",
        _make_module_id(),
        MagicMock(),
        [channel],
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id("cover", DOMAIN, UNIQUE_ID)
    assert entity_id is not None

    return entity_id, channel


async def test_cover_created_from_discovered_channel(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Discovering a Rollladen channel creates a cover entity."""
    entity_id, channel = await _setup_cover(hass, mock_home_server)

    state = hass.states.get(entity_id)
    assert state is not None
    # No status/configuration response has been received yet.
    assert state.attributes.get("current_position") is None

    # The entity requests hardware status once it is fully added to hass.
    channel.getStatus.assert_called_once()
    channel.getConfiguration.assert_called_once()


async def test_cover_handles_start_event(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """An EvStart event updates the opening/closing state."""
    entity_id, _channel = await _setup_cover(hass, mock_home_server)

    async_dispatcher_send(hass, UPDATE_SIGNAL, EvStart(EDirection.TO_OPEN))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "opening"

    async_dispatcher_send(hass, UPDATE_SIGNAL, EvStart(EDirection.TO_CLOSE))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "closing"


async def test_cover_handles_closed_event(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """An EvClosed event reports the cover as fully closed."""
    entity_id, _channel = await _setup_cover(hass, mock_home_server)

    async_dispatcher_send(hass, UPDATE_SIGNAL, EvClosed(100))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "closed"
    assert state.attributes["current_position"] == 0


async def test_cover_handles_open_event(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """An EvOpen event reports the cover as fully open."""
    entity_id, _channel = await _setup_cover(hass, mock_home_server)

    async_dispatcher_send(hass, UPDATE_SIGNAL, EvOpen())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "open"
    assert state.attributes["current_position"] == 100


async def test_cover_handles_status_event(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """A Status event reports the cover's current position."""
    entity_id, _channel = await _setup_cover(hass, mock_home_server)

    async_dispatcher_send(hass, UPDATE_SIGNAL, Status(40))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["current_position"] == 60
    assert state.state == "open"


async def test_cover_open_close_stop_and_set_position(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """Cover service calls translate to the right Haus-Bus channel calls."""
    entity_id, channel = await _setup_cover(hass, mock_home_server)

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": entity_id}, blocking=True
    )
    channel.start.assert_called_once_with(EDirection.TO_OPEN)

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": entity_id}, blocking=True
    )
    channel.start.assert_called_with(EDirection.TO_CLOSE)

    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": entity_id}, blocking=True
    )
    channel.stop.assert_called_once()

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 30},
        blocking=True,
    )
    channel.moveToPosition.assert_called_once_with(70)
