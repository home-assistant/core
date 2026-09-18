"""Tests for the LG Infrared event platform."""

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.codes.lg.tv import LGTVCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import RECEIVER_ENTITY_ID
from tests.components.infrared.common import MockInfraredReceiverEntity

EVENT_ENTITY_ID = "event.lg_tv_received_command"

_LG_TV_NEC_ADDRESS = 0xFB04


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.EVENT]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the event entity is created with the expected attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("command_byte", "expected_event_type"),
    [
        (LGTVCode.POWER_ON, "power_on"),
        (LGTVCode.POWER_OFF, "power_off"),
        (LGTVCode.VOLUME_UP, "volume_up"),
        (LGTVCode.MUTE, "mute"),
        (0xFE, "unknown"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_event_fires(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
    command_byte: int,
    expected_event_type: str,
) -> None:
    """Test the event entity fires the expected event type."""
    now = dt_util.parse_datetime("2026-05-12 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = NECCommand(address=_LG_TV_NEC_ADDRESS, command=command_byte)
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type


@pytest.mark.usefixtures("init_integration")
async def test_event_ignores_other_nec_addresses(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test the event entity ignores NEC signals from other addresses."""
    command = NECCommand(address=0x1234, command=LGTVCode.POWER_ON)
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPE) is None


@pytest.mark.usefixtures("init_integration")
async def test_event_ignores_non_nec_signals(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test the event entity ignores signals that cannot be decoded as NEC."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[1, 2, 3, 4])
    )
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPE) is None


@pytest.mark.usefixtures("init_integration")
async def test_event_resubscribes_after_receiver_unavailable(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the event entity resubscribes when the receiver becomes available again."""
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNKNOWN)
    await hass.async_block_till_done()
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    now = dt_util.parse_datetime("2026-05-12 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = NECCommand(address=_LG_TV_NEC_ADDRESS, command=LGTVCode.POWER_ON)
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "power_on"
