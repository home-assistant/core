"""Fixtures for elkm1 tests."""

from unittest.mock import MagicMock

from elkm1_lib.const import AlarmState, ArmedStatus, ArmUpState
from elkm1_lib.keypads import Keypad
import pytest

from homeassistant.components.elkm1.const import CONF_AUTO_CONFIGURE, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PREFIX, CONF_USERNAME

from . import MOCK_MAC, mock_elk

from tests.common import MockConfigEntry


class _AreaCollection:
    """Iterable area collection that also exposes an .elements attribute."""

    def __init__(self, areas: list) -> None:
        self.elements = areas

    def __iter__(self):
        return iter(self.elements)

    def __len__(self) -> int:
        return len(self.elements)


@pytest.fixture
def mock_area() -> MagicMock:
    """Return a mock Area element in a default disarmed state."""
    area = MagicMock()
    area.index = 0
    area.name = "Test Area"
    area.configured = True
    area.armed_status = ArmedStatus.DISARMED
    area.arm_up_state = ArmUpState.READY_TO_ARM
    area.alarm_state = AlarmState.NO_ALARM_ACTIVE
    area.timer1 = 0
    area.timer2 = 0
    area.is_exit = False
    area.last_log = None
    area.chime_mode = None
    area.alarm_memory = False
    area.in_alarm_state.return_value = False
    area.default_name.side_effect = lambda sep=" ": f"area{sep}1"
    area.as_dict.return_value = {}
    area._callbacks = []
    area.add_callback.side_effect = area._callbacks.append
    return area


@pytest.fixture
def mock_keypad() -> MagicMock:
    """Return a mock Keypad element that passes isinstance checks."""
    keypad = MagicMock()
    keypad.__class__ = Keypad
    keypad.area = 0
    keypad.name = "Test Keypad"
    keypad.last_user = 0
    keypad.last_user_time = MagicMock()
    keypad.last_user_time.isoformat.return_value = "2024-01-01T00:00:00"
    keypad._callbacks = []
    keypad.add_callback.side_effect = keypad._callbacks.append
    return keypad


@pytest.fixture
def mock_elk_instance(mock_area: MagicMock, mock_keypad: MagicMock) -> MagicMock:
    """Return a mock Elk instance wired up with a single area and keypad."""
    elk = mock_elk(sync_complete=True)
    areas = _AreaCollection([mock_area])
    elk.areas = areas
    elk.keypads = [mock_keypad]
    elk.panel.temperature_units = "F"
    elk.panel.elkm1_version = "1.0.0"
    elk.is_connected.return_value = True
    elk.users.username.return_value = "User 1"
    return elk


@pytest.fixture
def alarm_mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for a single auto-configured Elk-M1."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "elks://1.2.3.4",
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_PREFIX: "",
            CONF_AUTO_CONFIGURE: True,
        },
        unique_id=MOCK_MAC,
    )
