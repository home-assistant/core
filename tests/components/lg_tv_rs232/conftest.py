"""Test fixtures for the LG TV RS-232 integration."""

from unittest.mock import AsyncMock, patch

from lg_rs232_tv import LGTV, InputSource, PowerState, TVState
import pytest

from homeassistant.components.lg_tv_rs232.const import CONF_SET_ID, DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_SET_ID

from tests.common import MockConfigEntry


class MockLGTV(LGTV):
    """LG TV test double built on the real controller object."""

    def __init__(self, state: TVState) -> None:
        """Initialize the mock TV."""
        super().__init__(MOCK_DEVICE, set_id=MOCK_SET_ID)
        self._connected = True
        self._state = state
        self.connect = AsyncMock(side_effect=self._mock_connect)
        self.query = AsyncMock()
        self.disconnect = AsyncMock(side_effect=self._mock_disconnect)
        self.power_on = AsyncMock()
        self.power_off = AsyncMock()
        self.set_volume = AsyncMock()
        self.mute_on = AsyncMock()
        self.mute_off = AsyncMock()
        self.select_input_source = AsyncMock()

    def mock_state(self, state: TVState | None) -> None:
        """Push a state update through the TV."""
        self._connected = state is not None
        if state is not None:
            self._state = state
        self._notify_subscribers()

    async def _mock_connect(self) -> None:
        """Pretend to open the serial connection."""
        self._connected = True

    async def _mock_disconnect(self) -> None:
        """Pretend to close the serial connection."""
        self._connected = False
        self._notify_subscribers()


def _default_state() -> TVState:
    """Return a TVState with typical defaults."""
    return TVState(
        power=PowerState.ON,
        input_source=InputSource.HDMI1,
        volume=20,
        volume_mute=False,
        balance=50,
    )


@pytest.fixture
def initial_tv_state() -> TVState:
    """Return the initial TV state for a test."""
    return _default_state()


@pytest.fixture
def mock_lgtv(initial_tv_state: TVState) -> MockLGTV:
    """Create a mock LGTV controller."""
    return MockLGTV(initial_tv_state)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_SET_ID: MOCK_SET_ID},
        title="LG TV",
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
    mock_lgtv: MockLGTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Initialize the LG TV RS-232 component."""
    with patch(
        "homeassistant.components.lg_tv_rs232.LGTV",
        return_value=mock_lgtv,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
