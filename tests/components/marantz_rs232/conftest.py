"""Test fixtures for the Marantz RS-232 integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from marantz_rs232 import MarantzV2007Receiver, V2007Source
import pytest

from homeassistant.components.marantz_rs232.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_receiver() -> Generator[MarantzV2007Receiver]:
    """Use real player objects, populating state only when it is queried."""
    receiver = MarantzV2007Receiver(MOCK_DEVICE)

    async def connect() -> None:
        receiver._connected = True

    async def query_state() -> None:
        main = receiver._state.main
        main.power = True
        main.volume = -40.0
        main.mute = False
        main.source_audio = V2007Source.DVD.value

    async def query_multi_room() -> None:
        multi = receiver._state.multi_room_a
        multi.power = True
        multi.line_volume = -30.0
        multi.mute = False
        multi.source_audio = V2007Source.TV.value

    with (
        patch.object(receiver, "connect", side_effect=connect),
        patch.object(receiver, "query_state", side_effect=query_state),
        patch.object(receiver, "query_multi_room_a", side_effect=query_multi_room),
        patch.object(receiver, "_send_command", new_callable=AsyncMock),
        patch.object(receiver, "disconnect", wraps=receiver.disconnect),
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
    mock_receiver: MarantzV2007Receiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
