"""Test fixtures for the Denon RS232 integration."""

from __future__ import annotations

from typing import Literal
from unittest.mock import AsyncMock, patch

from denon_rs232 import (
    DenonReceiver,
    DigitalInputMode,
    InputSource,
    MainZoneState,
    ReceiverState,
    TunerBand,
    TunerMode,
    ZoneState,
)
from denon_rs232.models import MODELS
import pytest

from homeassistant.components.denon_rs232.config_flow import CONF_MODEL_NAME
from homeassistant.components.denon_rs232.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_MODEL

from tests.common import MockConfigEntry

ZoneName = Literal["main", "zone_2", "zone_3"]


class MockState(ReceiverState):
    """Receiver state with helpers for zone-oriented tests."""

    def get_zone(self, zone: ZoneName) -> ZoneState:
        """Return the requested zone state."""
        if zone == "main":
            return self.main_zone
        return getattr(self, zone)


class MockReceiver(DenonReceiver):
    """Receiver test double built on the real receiver/player objects."""

    def __init__(self, state: MockState) -> None:
        """Initialize the mock receiver."""
        super().__init__(MOCK_DEVICE, model=MODELS[MOCK_MODEL])
        self._connected = True
        self._load_state(state)
        self._send_command = AsyncMock()
        self._query = AsyncMock()
        self.connect = AsyncMock(side_effect=self._mock_connect)
        self.query_state = AsyncMock()
        self.disconnect = AsyncMock(side_effect=self._mock_disconnect)

    def get_zone(self, zone: ZoneName):
        """Return the matching live player object."""
        if zone == "main":
            return self.main
        if zone == "zone_2":
            return self.zone_2
        return self.zone_3

    def mock_state(self, state: MockState | None) -> None:
        """Push a state update through the receiver."""
        self._connected = state is not None
        if state is not None:
            self._load_state(state)
        self._notify_subscribers()

    async def _mock_connect(self) -> None:
        """Pretend to open the serial connection."""
        self._connected = True

    async def _mock_disconnect(self) -> None:
        """Pretend to close the serial connection."""
        self._connected = False
        self._notify_subscribers()

    def _load_state(self, state: MockState) -> None:
        """Swap in a new state object and rebind the live players to it."""
        self._state = state
        self.main._state = state.main_zone
        self.zone_2._state = state.zone_2
        self.zone_3._state = state.zone_3


def _default_state() -> MockState:
    """Return a ReceiverState with typical defaults."""
    return MockState(
        power=True,
        main_zone=MainZoneState(
            power=True,
            volume=-30.0,
            volume_min=-80,
            volume_max=10,
            mute=False,
            input_source=InputSource.CD,
            surround_mode="STEREO",
            digital_input=DigitalInputMode.AUTO,
            tuner_band=TunerBand.FM,
            tuner_mode=TunerMode.AUTO,
        ),
        zone_2=ZoneState(
            power=True,
            input_source=InputSource.TUNER,
            volume=-20.0,
        ),
        zone_3=ZoneState(
            power=False,
            input_source=InputSource.CD,
            volume=-35.0,
        ),
    )


@pytest.fixture
def initial_receiver_state(request: pytest.FixtureRequest) -> MockState:
    """Return the initial receiver state for a test."""
    state = _default_state()

    if getattr(request, "param", None) == "main_only":
        state.zone_2 = ZoneState()
        state.zone_3 = ZoneState()

    return state


@pytest.fixture
def mock_receiver(initial_receiver_state: MockState) -> MockReceiver:
    """Create a mock DenonReceiver."""
    return MockReceiver(initial_receiver_state)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE: MOCK_DEVICE,
            CONF_MODEL: MOCK_MODEL,
            CONF_MODEL_NAME: "AVR-3805",
        },
        title="AVR-3805",
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
    mock_receiver: MockReceiver,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Initialize the Denon component."""
    with patch(
        "homeassistant.components.denon_rs232.DenonReceiver",
        return_value=mock_receiver,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
