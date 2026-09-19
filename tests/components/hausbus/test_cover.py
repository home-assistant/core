"""Test the Haus-Bus cover platform."""

from unittest.mock import MagicMock

from pyhausbus.de.hausbus.homeassistant.proxy.Rollladen import Rollladen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvClosed import EvClosed
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvOpen import EvOpen
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.EvStart import EvStart
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.data.Status import Status
from pyhausbus.de.hausbus.homeassistant.proxy.rollladen.params.EDirection import (
    EDirection,
)
from pyhausbus.ObjectId import ObjectId
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.components.hausbus.const import DOMAIN, NEW_CHANNEL_ADDED
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry

_OBJECT_ID = 0x12345678


def _make_channel() -> MagicMock:
    """Return a fake Rollladen channel."""
    channel = MagicMock(spec=Rollladen)
    channel.getObjectId.return_value = _OBJECT_ID
    channel.getName.return_value = "Rolladen Wohnzimmer"
    return channel


def _entity_id(hass: HomeAssistant) -> str:
    """Return the entity_id of the (single) cover set up by cover_channel."""
    (entity_id,) = hass.states.async_entity_ids(COVER_DOMAIN)
    return entity_id


async def _send_event(hass: HomeAssistant, data: object) -> None:
    """Dispatch a hardware event for _OBJECT_ID, as gateway.busDataReceived() would."""
    async_dispatcher_send(
        hass, f"hausbus_update_{ObjectId(_OBJECT_ID).getValue()}", data
    )
    await hass.async_block_till_done()


@pytest.fixture
async def cover_channel(hass: HomeAssistant, mock_home_server: MagicMock) -> MagicMock:
    """Set up a config entry and add one cover through real channel discovery.

    Returns the fake hardware channel backing the created entity.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    channel = _make_channel()
    async_dispatcher_send(
        hass, NEW_CHANNEL_ADDED, channel, DeviceInfo(identifiers={(DOMAIN, "1")})
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    return channel


async def test_async_setup_entry_adds_only_rollladen_channels(
    hass: HomeAssistant, mock_home_server: MagicMock
) -> None:
    """async_setup_entry() only turns discovered Rollladen channels into covers."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_info = DeviceInfo(identifiers={(DOMAIN, "1")})
    async_dispatcher_send(hass, NEW_CHANNEL_ADDED, _make_channel(), device_info)
    async_dispatcher_send(hass, NEW_CHANNEL_ADDED, MagicMock(), device_info)
    await hass.async_block_till_done(wait_background_tasks=True)

    cover_entity_ids = hass.states.async_entity_ids("cover")
    assert len(cover_entity_ids) == 1

    # device_class is set by HausbusCover specifically, so this confirms the
    # created entity is really a HausbusCover and not some other platform's.
    state = hass.states.get(cover_entity_ids[0])
    assert state is not None
    assert state.attributes.get("device_class") == "shutter"


async def test_async_open_cover(hass: HomeAssistant, cover_channel: MagicMock) -> None:
    """Opening the cover starts it in the TO_OPEN direction."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: _entity_id(hass)},
        blocking=True,
    )
    cover_channel.start.assert_called_once_with(EDirection.TO_OPEN)


async def test_async_close_cover(hass: HomeAssistant, cover_channel: MagicMock) -> None:
    """Closing the cover starts it in the TO_CLOSE direction."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: _entity_id(hass)},
        blocking=True,
    )
    cover_channel.start.assert_called_once_with(EDirection.TO_CLOSE)


async def test_async_stop_cover(hass: HomeAssistant, cover_channel: MagicMock) -> None:
    """Stopping the cover clears the opening/closing flags."""
    entity_id = _entity_id(hass)

    await _send_event(hass, EvStart(EDirection.TO_OPEN))
    assert hass.states.get(entity_id).state == CoverState.OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    cover_channel.stop.assert_called_once()
    state = hass.states.get(entity_id).state
    assert state not in (CoverState.OPENING, CoverState.CLOSING)


async def test_async_set_cover_position_inverts_position(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """HA counts 0=closed/100=open; Haus-Bus counts the opposite, so it's inverted."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: _entity_id(hass), ATTR_POSITION: 30},
        blocking=True,
    )
    cover_channel.moveToPosition.assert_called_once_with(70)


async def test_handle_event_ev_start_to_open(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """An EvStart(TO_OPEN) event marks the cover as opening."""
    entity_id = _entity_id(hass)
    await _send_event(hass, EvStart(EDirection.TO_OPEN))
    assert hass.states.get(entity_id).state == CoverState.OPENING


async def test_handle_event_ev_start_to_close(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """An EvStart(TO_CLOSE) event marks the cover as closing."""
    entity_id = _entity_id(hass)
    await _send_event(hass, EvStart(EDirection.TO_CLOSE))
    assert hass.states.get(entity_id).state == CoverState.CLOSING


async def test_handle_event_ev_closed(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """An EvClosed event stops movement and sets the inverted position."""
    entity_id = _entity_id(hass)
    await _send_event(hass, EvStart(EDirection.TO_CLOSE))
    await _send_event(hass, EvClosed(100))

    state = hass.states.get(entity_id)
    assert state.state == CoverState.CLOSED
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 0


async def test_handle_event_ev_open(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """An EvOpen event stops movement and reports the cover as fully open."""
    entity_id = _entity_id(hass)
    await _send_event(hass, EvStart(EDirection.TO_OPEN))
    await _send_event(hass, EvOpen())

    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 100


async def test_handle_event_status_updates_position(
    hass: HomeAssistant, cover_channel: MagicMock
) -> None:
    """A Status event updates the reported position without touching movement flags."""
    entity_id = _entity_id(hass)
    await _send_event(hass, Status(40))
    assert hass.states.get(entity_id).attributes.get(ATTR_CURRENT_POSITION) == 60
