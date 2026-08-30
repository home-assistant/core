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
import pytest

from homeassistant.components.cover import ATTR_POSITION
from homeassistant.components.hausbus.const import DOMAIN, NEW_CHANNEL_ADDED
from homeassistant.components.hausbus.cover import HausbusCover
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


def _make_channel() -> MagicMock:
    """Return a fake Rollladen channel."""
    channel = MagicMock(spec=Rollladen)
    channel.getObjectId.return_value = 0x12345678
    channel.getName.return_value = "Rolladen Wohnzimmer"
    return channel


@pytest.fixture
def cover_entity(hass: HomeAssistant) -> HausbusCover:
    """Return a HausbusCover wired up to a fake channel, ready to write state."""
    entity = HausbusCover(_make_channel(), DeviceInfo(identifiers={(DOMAIN, "1")}))
    entity.hass = hass
    entity.entity_id = "cover.test"
    return entity


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


async def test_async_open_cover(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """Opening the cover starts it in the TO_OPEN direction."""
    await cover_entity.async_open_cover()
    cover_entity._channel.start.assert_called_once_with(EDirection.TO_OPEN)


async def test_async_close_cover(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """Closing the cover starts it in the TO_CLOSE direction."""
    await cover_entity.async_close_cover()
    cover_entity._channel.start.assert_called_once_with(EDirection.TO_CLOSE)


async def test_async_stop_cover(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """Stopping the cover clears the opening/closing flags."""
    cover_entity._attr_is_opening = True
    await cover_entity.async_stop_cover()
    cover_entity._channel.stop.assert_called_once()
    assert cover_entity.is_opening is False
    assert cover_entity.is_closing is False


async def test_async_set_cover_position_inverts_position(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """HA counts 0=closed/100=open; Haus-Bus counts the opposite, so it's inverted."""
    await cover_entity.async_set_cover_position(**{ATTR_POSITION: 30})
    cover_entity._channel.moveToPosition.assert_called_once_with(70)


async def test_handle_event_ev_start_to_open(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """An EvStart(TO_OPEN) event marks the cover as opening."""
    cover_entity.handle_event(EvStart(EDirection.TO_OPEN))
    assert cover_entity.is_opening is True
    assert cover_entity.is_closing is False


async def test_handle_event_ev_start_to_close(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """An EvStart(TO_CLOSE) event marks the cover as closing."""
    cover_entity.handle_event(EvStart(EDirection.TO_CLOSE))
    assert cover_entity.is_opening is False
    assert cover_entity.is_closing is True


async def test_handle_event_ev_closed(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """An EvClosed event stops movement and sets the inverted position."""
    cover_entity._attr_is_closing = True
    cover_entity.handle_event(EvClosed(100))
    assert cover_entity.current_cover_position == 0
    assert cover_entity.is_closed is True
    assert cover_entity.is_closing is False


async def test_handle_event_ev_open(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """An EvOpen event stops movement and reports the cover as fully open."""
    cover_entity._attr_is_opening = True
    cover_entity.handle_event(EvOpen())
    assert cover_entity.current_cover_position == 100
    assert cover_entity.is_closed is False
    assert cover_entity.is_opening is False


async def test_handle_event_status_updates_position(
    hass: HomeAssistant, cover_entity: HausbusCover
) -> None:
    """A Status event updates the reported position without touching movement flags."""
    cover_entity.handle_event(Status(40))
    assert cover_entity.current_cover_position == 60
