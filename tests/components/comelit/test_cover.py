"""Tests for Comelit SimpleHome cover platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import COVER, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comelit.const import (
    DEFAULT_COVER_TRAVEL_TIME,
    SCAN_INTERVAL,
)
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    snapshot_platform,
)

ENTITY_ID = "cover.cover0"


def _stopped_cover_device(index: int, name: str) -> ComelitSerialBridgeObject:
    """Return a cover device reporting the stopped status."""
    return ComelitSerialBridgeObject(
        index=index,
        name=name,
        status=0,
        human_status="stopped",
        type="cover",
        val=0,
        protected=0,
        zone="Open space",
        power=0.0,
        power_unit=WATT,
    )


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.BRIDGE_PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_serial_bridge_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_serial_bridge_config_entry.entry_id,
    )


async def test_cover_open(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover open service."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Finish opening, update status
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _stopped_cover_device(0, "Cover0"),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_close(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover close and stop service."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Close cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSING

    # Halfway through the estimated travel time
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 2))

    # Stop cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


async def test_cover_stop_if_stopped(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover stop service when already stopped."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # Stop cover while not opening/closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_not_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("cover_state", "cover_position"),
    [
        (CoverState.OPEN, 100),
        (CoverState.CLOSED, 0),
    ],
)
async def test_cover_restore_state(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    cover_state: CoverState,
    cover_position: int,
) -> None:
    """Test cover restore state on reload."""

    mock_restore_cache(hass, [State(ENTITY_ID, cover_state)])
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == cover_state
    assert state.attributes[ATTR_CURRENT_POSITION] == cover_position


async def test_cover_open_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover open and stop service."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING

    # Fully through the estimated travel time
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME))

    # Stop cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_position_estimation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover position is estimated from elapsed travel time."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Halfway through the estimated full travel time
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    # Device reports it finished opening on its own
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _stopped_cover_device(0, "Cover0"),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    # Close cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    # A quarter through the estimated full travel time
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_POSITION] == 75


@pytest.mark.parametrize(
    (
        "initial_state",
        "initial_position",
        "target_position",
        "transient_state",
    ),
    [
        pytest.param(CoverState.CLOSED, 0, 60, CoverState.OPENING, id="opening"),
        pytest.param(CoverState.OPEN, 100, 40, CoverState.CLOSING, id="closing"),
    ],
)
async def test_cover_set_position(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    initial_state: CoverState,
    initial_position: int,
    target_position: int,
    transient_state: CoverState,
) -> None:
    """Test setting a target position opens/closes and auto-stops at that position."""

    mock_restore_cache(hass, [State(ENTITY_ID, initial_state)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_POSITION] == initial_position

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: target_position},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == transient_state

    # Wait for the estimated time needed to reach the target position
    travel_seconds = (
        abs(target_position - initial_position) / 100 * DEFAULT_COVER_TRAVEL_TIME
    )
    freezer.tick(timedelta(seconds=travel_seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == target_position


async def test_cover_set_position_noop(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test setting the cover to its current position does nothing."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 0},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_not_called()


async def test_cover_set_position_cancels_previous_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test a new command cancels a previously scheduled automatic stop."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 30},
        blocking=True,
    )

    # Fully open before the scheduled stop for the 30% target would fire
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    calls_after_open = mock_serial_bridge.set_device_status.call_count

    # Advance well past when the cancelled 30% auto-stop would have fired
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == calls_after_open

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_dynamic(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test cover dynamically added."""

    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert hass.states.get(ENTITY_ID)

    entity_id_2 = "cover.cover1"

    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _stopped_cover_device(0, "Cover0"),
        1: _stopped_cover_device(1, "Cover1"),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(entity_id_2)
