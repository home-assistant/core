"""Test fixtures for the Sony TV RS-232 integration."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from sony_tv_rs232 import InputSource, PowerState, SonyTV, SoundMode, TVState

from homeassistant.components.sony_tv_rs232.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from . import MOCK_PORT


class MockSonyTV(SonyTV):
    """Sony TV test double built on the real controller object.

    Commands are AsyncMocks; the query mocks answer from ``state`` so a poll
    sees whatever the test put there. ``supports_queries`` is what the real
    handshake would have probed.
    """

    def __init__(self, state: TVState, *, supports_queries: bool = True) -> None:
        """Initialize the mock TV."""
        super().__init__(MOCK_PORT)
        self.state = state
        self._connected = False
        self._supports_queries = supports_queries
        self.connect = AsyncMock(side_effect=self._mock_connect)
        self.disconnect = AsyncMock(side_effect=self._mock_disconnect)
        self.query_power = AsyncMock(side_effect=lambda: self.state.power)
        self.query_input_source = AsyncMock(side_effect=lambda: self.state.input_source)
        self.query_volume = AsyncMock(side_effect=lambda: self.state.volume)
        self.query_mute = AsyncMock(side_effect=lambda: self.state.audio_mute)
        self.query_sound_mode = AsyncMock(side_effect=lambda: self.state.sound_mode)
        self.power_on = AsyncMock()
        self.power_off = AsyncMock()
        self.set_volume = AsyncMock()
        self.volume_up = AsyncMock()
        self.volume_down = AsyncMock()
        self.mute_on = AsyncMock()
        self.mute_off = AsyncMock()
        self.select_input_source = AsyncMock()
        self.set_sound_mode = AsyncMock()

    @property
    def connected(self) -> bool:
        """Return whether the pretend serial connection is open."""
        return self._connected

    def mock_state(self, state: TVState | None) -> None:
        """Push a state notification through the TV (None = link dropped)."""
        self._connected = state is not None
        if state is not None:
            self.state = state
        self._deliver(state)

    async def _mock_connect(self) -> None:
        """Pretend to open the serial connection."""
        self._connected = True

    async def _mock_disconnect(self) -> None:
        """Pretend to close the serial connection."""
        self._connected = False
        self._deliver(None)


def default_state() -> TVState:
    """Return a TVState for a TV that is on."""
    return TVState(
        power=PowerState.ON,
        input_source=InputSource.HDMI1,
        volume=20,
        audio_mute=False,
        sound_mode=SoundMode.STANDARD,
    )


@pytest.fixture
def initial_tv_state() -> TVState:
    """Return the initial TV state for a test."""
    return default_state()


@pytest.fixture
def supports_queries() -> bool:
    """Return whether the mock TV answers queries (a Pro Bravia does)."""
    return True


@pytest.fixture
def mock_sony_tv(initial_tv_state: TVState, supports_queries: bool) -> MockSonyTV:
    """Create a mock SonyTV controller."""
    return MockSonyTV(initial_tv_state, supports_queries=supports_queries)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: MOCK_PORT},
        title="Sony TV",
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
async def mock_usb_component(hass: HomeAssistant) -> None:
    """Mock the USB component to prevent setup failures."""
    hass.config.components.add("usb")


@pytest.fixture
async def init_components(
    hass: HomeAssistant,
    mock_usb_component: None,
    mock_sony_tv: MockSonyTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Initialize the Sony TV RS-232 component."""
    with patch(
        "homeassistant.components.sony_tv_rs232.SonyTV",
        return_value=mock_sony_tv,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
