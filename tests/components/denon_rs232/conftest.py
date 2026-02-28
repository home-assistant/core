"""Test fixtures for the Denon RS232 integration."""

from unittest.mock import AsyncMock, MagicMock

from denon_rs232 import (
    DenonReceiver,
    DenonState,
    DigitalInputMode,
    InputSource,
    PowerState,
    TunerBand,
    TunerMode,
)
from denon_rs232.models import MODELS
import pytest

from homeassistant.components.denon_rs232.const import CONF_MODEL, DOMAIN
from homeassistant.const import CONF_PORT

from tests.common import MockConfigEntry

MOCK_PORT = "/dev/ttyUSB0"
MOCK_MODEL = "avr_3805"


def _default_state() -> DenonState:
    """Return a DenonState with typical defaults."""
    return DenonState(
        power=PowerState.ON,
        main_zone=True,
        volume=-30.0,
        mute=False,
        input_source=InputSource.CD,
        surround_mode="STEREO",
        digital_input=DigitalInputMode.AUTO,
        tuner_band=TunerBand.FM,
        tuner_mode=TunerMode.AUTO,
    )


@pytest.fixture
def mock_receiver() -> MagicMock:
    """Create a mock DenonReceiver."""
    receiver = MagicMock(spec=DenonReceiver)
    receiver.connect = AsyncMock()
    receiver.disconnect = AsyncMock()
    receiver.power_on = AsyncMock()
    receiver.power_standby = AsyncMock()
    receiver.set_volume = AsyncMock()
    receiver.volume_up = AsyncMock()
    receiver.volume_down = AsyncMock()
    receiver.mute_on = AsyncMock()
    receiver.mute_off = AsyncMock()
    receiver.select_input_source = AsyncMock()
    receiver.set_surround_mode = AsyncMock()
    receiver.connected = True
    receiver.state = _default_state()
    receiver.model = MODELS[MOCK_MODEL]
    receiver.subscribe = MagicMock(return_value=MagicMock())
    return receiver


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: MOCK_PORT, CONF_MODEL: MOCK_MODEL},
        title=f"Denon AVR-3805 / AVC-3890 ({MOCK_PORT})",
    )
