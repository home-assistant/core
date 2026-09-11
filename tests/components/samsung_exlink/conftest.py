"""Test fixtures for the Samsung ExLink integration."""

from unittest.mock import AsyncMock, patch

import pytest
from samsung_exlink import MODELS, InputSource, PowerState, SamsungTV, TVState

from homeassistant.components.samsung_exlink.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_MODEL

from tests.common import MockConfigEntry


class MockSamsungTV(SamsungTV):
    """Samsung TV test double built on the real controller object."""

    def __init__(self, state: TVState) -> None:
        """Initialize the mock TV."""
        super().__init__(MOCK_DEVICE, model=MODELS[MOCK_MODEL])
        self._connected = True
        self._state = state
        self.connect = AsyncMock(side_effect=self._mock_connect)
        self.refresh = AsyncMock()
        self.query_power = AsyncMock(return_value=PowerState.ON)
        self.disconnect = AsyncMock(side_effect=self._mock_disconnect)
        self.power_on = AsyncMock()
        self.power_off = AsyncMock()
        self.set_volume = AsyncMock()
        self.set_mute = AsyncMock()
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
        power=True,
        input_source=InputSource.HDMI1,
        volume=20,
        mute=False,
    )


@pytest.fixture
def initial_tv_state() -> TVState:
    """Return the initial TV state for a test."""
    return _default_state()


@pytest.fixture
def mock_samsung_tv(initial_tv_state: TVState) -> MockSamsungTV:
    """Create a mock SamsungTV controller."""
    return MockSamsungTV(initial_tv_state)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: MOCK_DEVICE, CONF_MODEL: MOCK_MODEL},
        title="Samsung TV",
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
    mock_samsung_tv: MockSamsungTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Initialize the Samsung ExLink component."""
    with patch(
        "homeassistant.components.samsung_exlink.SamsungTV",
        return_value=mock_samsung_tv,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
