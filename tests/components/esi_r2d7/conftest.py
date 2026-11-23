"""Test fixtures for the ESI R2D7 integration."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.esi_r2d7.const import (
    CONF_FIRST_CHANNEL,
    CONF_LAST_CHANNEL,
    CONF_SYSTEM,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE


class MockConnection:
    """R2D7Connection test double."""

    def __init__(self) -> None:
        """Initialize the mock connection."""
        self.connected = False
        self.recently_moved: set[int] = set()
        self._listeners: list[Callable[[], None]] = []
        self.connect = AsyncMock(side_effect=self._mock_connect)
        self.disconnect = AsyncMock(side_effect=self._mock_disconnect)
        self.open_blind = AsyncMock()
        self.close_blind = AsyncMock()
        self.stop_system = AsyncMock()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a link listener."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def take_recently_moved(self, window: float) -> set[int]:
        """Return the channels moved recently."""
        moved, self.recently_moved = self.recently_moved, set()
        return moved

    def mock_link(self, connected: bool) -> None:
        """Push a link change to the listeners."""
        self.connected = connected
        for listener in list(self._listeners):
            listener()

    async def _mock_connect(self) -> None:
        self.connected = True

    async def _mock_disconnect(self) -> None:
        self.mock_link(False)


@pytest.fixture
def mock_connection() -> Generator[MockConnection]:
    """Patch R2D7Connection in the integration and the config flow."""
    connection = MockConnection()
    with (
        patch(
            "homeassistant.components.esi_r2d7.R2D7Connection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.esi_r2d7.config_flow.R2D7Connection",
            return_value=connection,
        ),
    ):
        yield connection


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry with channels 1 to 3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ESI R2D7 system 1",
        data={
            CONF_DEVICE: MOCK_DEVICE,
            CONF_SYSTEM: 1,
            CONF_FIRST_CHANNEL: 1,
            CONF_LAST_CHANNEL: 3,
        },
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
async def mock_usb_component(hass: HomeAssistant) -> None:
    """Mock the USB component to prevent setup failures."""
    hass.config.components.add("usb")


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
