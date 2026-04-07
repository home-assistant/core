"""Tests for the LG Infrared event platform."""

from __future__ import annotations

from unittest.mock import patch

from infrared_protocols import NECCommand, Timing
from infrared_protocols.codes.lg.tv import LGTVCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.infrared import (
    DATA_COMPONENT as INFRARED_DATA_COMPONENT,
    DOMAIN as INFRARED_DOMAIN,
    InfraredReceivedSignal,
)
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_INFRARED_ENTITY_ID,
    MOCK_INFRARED_RECEIVER_ENTITY_ID,
    MockInfraredEntity,
    MockInfraredReceiverEntity,
)
from .utils import check_availability_follows_ir_entity

from tests.common import MockConfigEntry, snapshot_platform

EVENT_ENTITY_ID = "event.lg_tv_received_command"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.EVENT]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with receiver configured."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="LG TV via Test IR transmitter",
        data={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
        unique_id=f"lg_ir_tv_{MOCK_INFRARED_ENTITY_ID}",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_make_lg_tv_command: None,
) -> MockConfigEntry:
    """Set up LG Infrared integration with receiver for testing."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()

    infrared_component = hass.data[INFRARED_DATA_COMPONENT]
    await infrared_component.async_add_entities(
        [mock_infrared_entity, mock_infrared_receiver_entity]
    )

    mock_config_entry.add_to_hass(hass)

    # Patch base PLATFORMS to empty so only the conditionally-added EVENT loads
    with patch("homeassistant.components.lg_infrared.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


def _make_lg_tv_signal(code: LGTVCode) -> InfraredReceivedSignal:
    """Create an InfraredReceivedSignal for an LG TV command."""
    timings = NECCommand(
        address=0xFB04, command=code.value, modulation=38000
    ).get_raw_timings()
    return InfraredReceivedSignal(timings=timings, modulation=38000)


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test event entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify entity belongs to the correct device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("init_integration")
async def test_receives_known_lg_tv_command(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test event fires when a known LG TV IR command is received."""
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    signal = _make_lg_tv_signal(LGTVCode.POWER)
    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPE] == "power"


@pytest.mark.usefixtures("init_integration")
async def test_receives_volume_up_command(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test event fires with correct type for volume up command."""
    signal = _make_lg_tv_signal(LGTVCode.VOLUME_UP)
    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "volume_up"


@pytest.mark.usefixtures("init_integration")
async def test_receives_unknown_lg_command(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test event fires as 'unknown' for unrecognized LG TV command code."""
    # Use command byte 0xFE which is not in LGTVCode
    timings = NECCommand(
        address=0xFB04, command=0xFE, modulation=38000
    ).get_raw_timings()
    signal = InfraredReceivedSignal(timings=timings, modulation=38000)

    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "unknown"


@pytest.mark.usefixtures("init_integration")
async def test_ignores_non_lg_address(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that signals from a non-LG NEC address are ignored."""
    timings = NECCommand(
        address=0x1234, command=0x08, modulation=38000
    ).get_raw_timings()
    signal = InfraredReceivedSignal(timings=timings, modulation=38000)

    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_ignores_non_nec_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that non-NEC signals are ignored."""
    # Send garbage timings that don't match NEC protocol
    signal = InfraredReceivedSignal(
        timings=[Timing(high_us=100, low_us=100)] * 10,
        modulation=38000,
    )

    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_event_entity_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test event entity becomes unavailable when IR emitter entity is unavailable."""
    await check_availability_follows_ir_entity(hass, EVENT_ENTITY_ID)
