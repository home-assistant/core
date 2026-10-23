"""Test fixtures for the Marantz RS-232 integration."""

from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

from marantz_rs232 import (
    MarantzV2007Receiver,
    V2007MainPlayer,
    V2007MultiRoomPlayer,
    V2007ReceiverState,
    V2007Source,
)
import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE

from tests.common import MockConfigEntry


@pytest.fixture
def receiver_callbacks() -> list[Callable[[V2007ReceiverState | None], None]]:
    """Track subscriptions made through the receiver's public API."""
    return []


@pytest.fixture
def receiver_update(
    receiver_callbacks: list[Callable[[V2007ReceiverState | None], None]],
) -> Callable[[V2007ReceiverState | None], None]:
    """Deliver receiver events to the registered callbacks."""

    def update(state: V2007ReceiverState | None) -> None:
        for callback in tuple(receiver_callbacks):
            callback(state)

    return update


@pytest.fixture
def mock_receiver(
    receiver_callbacks: list[Callable[[V2007ReceiverState | None], None]],
    receiver_update: Callable[[V2007ReceiverState | None], None],
) -> Generator[MagicMock]:
    """Mock the receiver and players at their public API boundary."""
    receiver = MagicMock(spec=MarantzV2007Receiver, connected=False)
    receiver.main = MagicMock(
        spec=V2007MainPlayer,
        power=True,
        volume=-40.0,
        mute=False,
        input_source=V2007Source.DVD,
    )
    receiver.multi_room_a = MagicMock(
        spec=V2007MultiRoomPlayer,
        power=True,
        line_volume=-30.0,
        mute=False,
        input_source=V2007Source.TV,
    )

    async def connect() -> None:
        receiver.connected = True

    async def disconnect() -> None:
        receiver.connected = False
        receiver_update(None)

    def subscribe(
        callback: Callable[[V2007ReceiverState | None], None],
    ) -> Callable[[], None]:
        receiver_callbacks.append(callback)
        return lambda: receiver_callbacks.remove(callback)

    receiver.connect.side_effect = connect
    receiver.disconnect.side_effect = disconnect
    receiver.subscribe.side_effect = subscribe
    with (
        patch(
            "homeassistant.components.marantz_rs232.MarantzV2007Receiver",
            return_value=receiver,
        ),
        patch(
            "homeassistant.components.marantz_rs232.config_flow.MarantzV2007Receiver",
            return_value=receiver,
        ),
    ):
        yield receiver


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE},
        title="Marantz receiver",
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )


@pytest.fixture(autouse=True)
def mock_usb_component(hass: HomeAssistant) -> None:
    """Avoid scanning serial devices."""
    hass.config.components.add("usb")


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
