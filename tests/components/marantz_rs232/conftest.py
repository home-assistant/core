"""Test fixtures for the Marantz RS-232 integration."""

from unittest.mock import AsyncMock, patch

from marantz_rs232 import (
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
    V2003Source,
    V2007Model,
    V2007Source,
    V2015InputSource,
)
import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE

from tests.common import MockConfigEntry


def push_state(receiver: object) -> None:
    """Notify subscribers using whichever notify API the protocol exposes."""
    # The v2003 protocol takes the state explicitly; the others read self._state.
    if hasattr(receiver, "_notify_subscribers"):
        receiver._notify_subscribers()
    else:
        receiver._notify(receiver._state if receiver._connected else None)


def _install_async_mocks(receiver: object) -> object:
    """Replace the serial I/O surface with awaitable mocks."""
    receiver._connected = True
    receiver.connect = AsyncMock()
    receiver.query_state = AsyncMock()
    receiver._send_command = AsyncMock()

    async def _disconnect() -> None:
        receiver._connected = False
        push_state(receiver)

    receiver.disconnect = AsyncMock(side_effect=_disconnect)
    return receiver


@pytest.fixture
def mock_v2015_receiver() -> MarantzV2015Receiver:
    """Create a modern (2015+) Marantz receiver test double."""
    receiver = MarantzV2015Receiver(MOCK_DEVICE)

    main = receiver._state.main_zone
    main.power = True
    main.volume = -40.0
    main.volume_min = -80.0
    main.volume_max = 18.0
    main.mute = False
    main.input_source = V2015InputSource.CD

    zone_2 = receiver._state.zone_2
    zone_2.power = True
    zone_2.volume = -30.0
    zone_2.input_source = V2015InputSource.TUNER

    zone_3 = receiver._state.zone_3
    zone_3.power = False
    zone_3.input_source = V2015InputSource.NET

    return _install_async_mocks(receiver)


@pytest.fixture
def mock_v2007_receiver() -> MarantzV2007Receiver:
    """Create a 2007-era Marantz receiver test double."""
    receiver = MarantzV2007Receiver(MOCK_DEVICE, model=V2007Model.SR7002)

    main = receiver._state.main
    main.power = True
    main.volume = -40.0
    main.mute = False
    main.source_audio = V2007Source.DVD.value

    multi_room = receiver._state.multi_room_a
    multi_room.power = True
    multi_room.line_volume = -30.0
    multi_room.mute = False
    multi_room.source_audio = V2007Source.TV.value

    return _install_async_mocks(receiver)


@pytest.fixture
def mock_v2003_receiver() -> MarantzV2003Receiver:
    """Create a 2003-era Marantz receiver test double."""
    receiver = MarantzV2003Receiver(MOCK_DEVICE)

    main = receiver._state.main
    main.power = True
    main.volume = -40.0
    main.mute = False
    main.audio_input = V2003Source.CD

    multi_room = receiver._state.multi_room
    multi_room.enabled = True
    multi_room.volume = -30.0
    multi_room.audio_input = V2003Source.TUNER

    return _install_async_mocks(receiver)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for the modern receiver."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: "modern"},
        title="Modern",
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )


@pytest.fixture(autouse=True)
def mock_usb_component(hass: HomeAssistant) -> None:
    """Mock the USB component to prevent setup failures."""
    hass.config.components.add("usb")


async def setup_integration(
    hass: HomeAssistant,
    entry: ConfigEntry,
    receiver: object,
    receiver_class: str,
) -> None:
    """Set up the integration with a mocked receiver class."""
    entry.add_to_hass(hass)
    with patch(
        f"homeassistant.components.marantz_rs232.{receiver_class}",
        return_value=receiver,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
