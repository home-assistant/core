"""Tests for Comelit SimpleHome cover platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiocomelit import CannotConnect
from aiocomelit.api import ComelitDeviceObject
from aiocomelit.const import COVER, STATE_COVER, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.comelit.const import (
    CONF_TRAVEL_TIME,
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "cover.cover0"
UNIQUE_ID = "serial_bridge_config_entry_id-0"


def _cover_device(index: int, name: str, status: int = 0) -> ComelitDeviceObject:
    """Return a cover device reporting the given status."""
    return ComelitDeviceObject(
        index=index,
        name=name,
        status=status,
        human_status=STATE_COVER[status],
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
        0: _cover_device(0, "Cover0"),
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
    ("cover_state", "attributes", "cover_position"),
    [
        pytest.param(CoverState.OPEN, {}, 100, id="open"),
        pytest.param(CoverState.CLOSED, {}, 0, id="closed"),
        pytest.param(
            CoverState.OPEN, {ATTR_CURRENT_POSITION: 40}, 40, id="partially_open"
        ),
    ],
)
async def test_cover_restore_state(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    cover_state: CoverState,
    attributes: dict[str, int],
    cover_position: int,
) -> None:
    """Test cover restore state on reload."""

    mock_restore_cache(hass, [State(ENTITY_ID, cover_state, attributes)])
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
        0: _cover_device(0, "Cover0"),
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

    mock_restore_cache(
        hass, [State(ENTITY_ID, CoverState.OPEN, {ATTR_CURRENT_POSITION: 40})]
    )
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 40},
        blocking=True,
    )
    mock_serial_bridge.set_device_status.assert_not_called()


@pytest.mark.parametrize(
    ("restored_states", "target_position", "transient_state"),
    [
        pytest.param([], 0, CoverState.CLOSING, id="unknown_close"),
        pytest.param(
            [State(ENTITY_ID, CoverState.OPEN)], 0, CoverState.CLOSING, id="close"
        ),
        pytest.param(
            [State(ENTITY_ID, CoverState.CLOSED)], 100, CoverState.OPENING, id="open"
        ),
    ],
)
async def test_cover_set_position_full_travel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    restored_states: list[State],
    target_position: int,
    transient_state: CoverState,
) -> None:
    """Test fully opening or closing leaves stopping to the motor end stop."""

    mock_restore_cache(hass, restored_states)
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: target_position},
        blocking=True,
    )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == transient_state

    # No stop command is scheduled, even well past the estimated travel time
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME * 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == 1


async def test_cover_set_position_already_stopped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test no stop command is sent if the cover stopped before the timer fired."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 10},
        blocking=True,
    )

    # Stopped before any poll saw it, e.g. at its end stop
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _cover_device(0, "Cover0"),
    }

    # Shorter than the poll interval, so only the scheduled stop sees it
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == 1

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 10


async def test_cover_set_position_current_while_moving(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test requesting the current position of a moving cover stops it."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME * 0.4))

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 40},
        blocking=True,
    )

    assert mock_serial_bridge.set_device_status.call_count == 2

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 40


async def test_cover_set_position_refresh_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test no stop command is sent when the status cannot be refreshed."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 10},
        blocking=True,
    )

    mock_serial_bridge.get_all_devices.side_effect = CannotConnect

    # Shorter than the poll interval, so only the scheduled stop refreshes
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == 1


async def test_cover_set_position_superseded_during_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test a command accepted during the scheduled stop refresh is not stopped."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 10},
        blocking=True,
    )

    devices = mock_serial_bridge.get_all_devices.return_value

    async def _open_during_refresh() -> dict:
        mock_serial_bridge.get_all_devices.side_effect = None
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        return devices

    mock_serial_bridge.get_all_devices.side_effect = _open_during_refresh

    # Shorter than the poll interval, so only the scheduled stop refreshes
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME / 10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == 2

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.OPENING


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


async def test_cover_external_movement(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test movements started outside Home Assistant are tracked."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.OPEN)])
    await setup_integration(hass, mock_serial_bridge_config_entry)

    # Closed from the wall switch
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _cover_device(0, "Cover0", STATE_COVER.index("closing")),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    # Reaches its end stop sooner than the default travel time estimates
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _cover_device(0, "Cover0"),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_cover_external_reversal(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test a reversal outside Home Assistant replaces the requested movement."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    mock_serial_bridge.reset_mock()
    await setup_integration(hass, mock_serial_bridge_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 60},
        blocking=True,
    )

    # Reversed from the wall switch
    mock_serial_bridge.get_all_devices.return_value[COVER] = {
        0: _cover_device(0, "Cover0", STATE_COVER.index("closing")),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_POSITION] == 20

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # The scheduled stop for the 60% target was cancelled
    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_serial_bridge.set_device_status.call_count == 1


async def test_cover_command_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test a failed command does not record a movement."""

    mock_restore_cache(hass, [State(ENTITY_ID, CoverState.CLOSED)])
    await setup_integration(hass, mock_serial_bridge_config_entry)

    mock_serial_bridge.set_device_status.side_effect = CannotConnect
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_cover_configured_travel_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test the travel time configured for the cover unique ID is used."""

    await setup_integration(hass, mock_serial_bridge_config_entry)
    hass.config_entries.async_update_entry(
        mock_serial_bridge_config_entry,
        options={CONF_TRAVEL_TIME: {UNIQUE_ID: DEFAULT_COVER_TRAVEL_TIME * 2}},
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    freezer.tick(timedelta(seconds=DEFAULT_COVER_TRAVEL_TIME))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


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
        0: _cover_device(0, "Cover0"),
        1: _cover_device(1, "Cover1"),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(entity_id_2)
