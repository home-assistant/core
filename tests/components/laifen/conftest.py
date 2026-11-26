"""Common fixtures for the Laifen tests."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from laifen_ble import BrushingSession, LaifenState, Mode, ModeSettings
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.laifen import PLATFORMS
from homeassistant.components.laifen.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from . import ADDRESS, NAME, setup_integration, wake_up

FIRMWARE_VERSION = "V2.0.93.XXX.T01.B00.Y44.303"
SESSION = BrushingSession(
    started_at=datetime(2026, 11, 26, 7, 30, tzinfo=UTC), duration=124
)

STATE = LaifenState(
    mode=Mode.MODE_2,
    mode_settings={
        Mode.MODE_1: ModeSettings(strength=1, range=10, speed=7),
        Mode.MODE_2: ModeSettings(strength=8, range=5, speed=3),
        Mode.MODE_3: ModeSettings(strength=4, range=10, speed=10),
        Mode.HIGH_FREQUENCY: ModeSettings(strength=20, range=1, speed=1),
    },
    airplane_mode=False,
    battery_level=93,
    reminder_30s=False,
    brushing_time=120,
    high_frequency=True,
    running=False,
)


@pytest.fixture(autouse=True)
def auto_enable_bluetooth(enable_bluetooth: None) -> None:
    """Enable Bluetooth for all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.laifen.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_ADDRESS: ADDRESS},
        unique_id=ADDRESS,
    )


@pytest.fixture
def mock_toothbrush_class() -> Generator[MagicMock]:
    """Return the mocked toothbrush class."""
    with (
        patch(
            "homeassistant.components.laifen.LaifenToothbrush", autospec=True
        ) as toothbrush_class,
        patch(
            "homeassistant.components.laifen.config_flow.LaifenToothbrush",
            new=toothbrush_class,
        ),
    ):
        yield toothbrush_class


@pytest.fixture
def last_session() -> BrushingSession | None:
    """Return the last brushing session of the toothbrush."""
    return None


@pytest.fixture
def mock_toothbrush(
    mock_toothbrush_class: MagicMock, last_session: BrushingSession | None
) -> MagicMock:
    """Return a mocked toothbrush that connects and reports its state."""
    toothbrush = mock_toothbrush_class.return_value
    toothbrush.address = ADDRESS
    toothbrush.name = NAME
    toothbrush.connected = False
    toothbrush.state = None
    toothbrush.firmware_version = None
    toothbrush.last_session = last_session
    callbacks: list[Callable[[], None]] = []

    def register_callback(callback: Callable[[], None]) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: callbacks.remove(callback)

    def notify() -> None:
        for callback in callbacks:
            callback()

    async def connect() -> None:
        toothbrush.connected = True
        toothbrush.state = STATE
        toothbrush.firmware_version = FIRMWARE_VERSION
        notify()

    async def disconnect() -> None:
        toothbrush.connected = False
        notify()

    toothbrush.register_callback.side_effect = register_callback
    toothbrush.connect.side_effect = connect
    toothbrush.disconnect.side_effect = disconnect
    toothbrush.notify = notify
    return toothbrush


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return list(PLATFORMS)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_toothbrush: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration with an awake toothbrush."""
    with patch("homeassistant.components.laifen.PLATFORMS", platforms):
        await setup_integration(hass, mock_config_entry)
    await wake_up(hass)
    return mock_config_entry
