"""Tests for the Gaposa cover platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverEntityFeature,
)
from homeassistant.components.gaposa.const import MOTION_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

LIVING_ROOM_ENTITY = "cover.living_room"
BEDROOM_ENTITY = "cover.bedroom"


async def test_cover_entities_created(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Both mock motors should produce cover entities at setup."""
    living_room = hass.states.get(LIVING_ROOM_ENTITY)
    bedroom = hass.states.get(BEDROOM_ENTITY)

    assert living_room is not None
    assert bedroom is not None


async def test_cover_initial_state_from_motor(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The Living Room motor is UP, the Bedroom motor is DOWN."""
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_CLOSED


async def test_cover_supported_features(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Open, close and stop are all supported; no position control."""
    state = hass.states.get(LIVING_ROOM_ENTITY)
    expected = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected
    # Covers without position support should not expose current_position.
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_open_cover_calls_motor_up(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling open_cover invokes the mocked Motor.up()."""
    living_room_motor = mock_motors[0]  # id="motor-1", "Living Room"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    living_room_motor.up.assert_called_once()


async def test_close_cover_calls_motor_down(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling close_cover invokes the mocked Motor.down()."""
    bedroom_motor = mock_motors[1]  # id="motor-2", "Bedroom"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    bedroom_motor.down.assert_called_once()


async def test_stop_cover_calls_motor_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling stop_cover invokes the mocked Motor.stop()."""
    living_room_motor = mock_motors[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    living_room_motor.stop.assert_called_once()


async def test_stop_cancels_pending_motion_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A stop command mid-motion cancels the pending motion refresh.

    Without this the open/close command's scheduled callback sits waiting
    until MOTION_DELAY elapses and then fires a pointless coordinator
    refresh long after the user has already stopped the cover.
    """
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )

    # The entity should have an active cancel handle for the motion refresh.
    entity = hass.data["entity_components"]["cover"].get_entity(BEDROOM_ENTITY)
    assert entity._cancel_motion_refresh is not None
    # Stop cancels it.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entity._cancel_motion_refresh is None


async def test_cover_reports_opening_during_motion_window(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """After an open command the cover state is `opening` until MOTION_DELAY elapses."""
    now = dt_util.utcnow()

    with freeze_time(now):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: BEDROOM_ENTITY},
            blocking=True,
        )

    assert hass.states.get(BEDROOM_ENTITY).state == STATE_OPENING


async def test_cover_reports_closing_during_motion_window(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """After a close command the cover state is `closing` until MOTION_DELAY elapses."""
    now = dt_util.utcnow()

    with freeze_time(now):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
            blocking=True,
        )

    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_CLOSING


@pytest.mark.parametrize(
    ("motor_state", "expected"),
    [
        ("UP", STATE_OPEN),
        ("DOWN", STATE_CLOSED),
        ("STOP", STATE_UNKNOWN),
        ("UNKNOWN", STATE_UNKNOWN),
    ],
)
async def test_cover_state_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
    motor_state: str,
    expected: str,
) -> None:
    """Verify the motor.state → HA state mapping across known + unknown values."""
    motor = mock_motors[0]
    motor.state = motor_state

    # Poke the coordinator so the entity re-reads motor state.
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_ROOM_ENTITY).state == expected


async def test_cover_device_registry_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Each motor ends up as a distinct device in the registry."""
    device_registry = dr.async_get(hass)
    # Two motors → two devices.
    gaposa_devices = [
        d
        for d in device_registry.devices.values()
        if any(i[0] == "gaposa" for i in d.identifiers)
    ]
    assert len(gaposa_devices) == 2
    names = {d.name for d in gaposa_devices}
    assert names == {"Living Room", "Bedroom"}


async def test_entity_reads_state_from_current_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Entity state should come from coordinator.data, not a cached Motor.

    pygaposa 0.2.4 happens to mutate Motor instances in place on refresh,
    but we don't want to rely on that — if the library ever starts
    returning fresh instances each refresh, cached references would go
    stale. This test proves the entity re-reads through coordinator.data
    by replacing the Motor object entirely and confirming the new state
    shows up.
    """
    # Living Room starts with state UP → HA state `open`.
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN

    coordinator = init_integration.runtime_data
    original_key = "DEVICE123.motors.motor-1"
    assert original_key in coordinator.data

    # Build a brand-new Motor-shaped mock with state DOWN and swap it in.
    replacement = MagicMock()
    replacement.id = "motor-1"
    replacement.name = "Living Room"
    replacement.state = "DOWN"
    coordinator.data[original_key] = replacement
    # Notify listeners so the entity writes its state.
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # The entity should report the replacement's state, not the
    # original mock_motors[0]'s state.
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_CLOSED


async def test_stale_motor_cleans_up_entity_and_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
) -> None:
    """Removing a motor drops both the entity and device registry entries.

    The integration explicitly removes the entity via
    entity_registry.async_remove and the device via
    device_registry.async_remove_device so neither lingers as an
    orphan after a motor disappears from the Gaposa account.
    """
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    # Sanity: both covers start with entity + device entries.
    assert entity_registry.async_get(LIVING_ROOM_ENTITY) is not None
    assert entity_registry.async_get(BEDROOM_ENTITY) is not None
    bedroom_device = device_registry.async_get_device(
        identifiers={("gaposa", "DEVICE123.motors.motor-2")}
    )
    assert bedroom_device is not None

    # Simulate the Bedroom motor having been removed from the user's
    # Gaposa account: drop it from the mocked pygaposa device.
    client, _user = mock_gaposa_instance.clients[0]
    device = client.devices[0]
    device.motors = [m for m in device.motors if m.id != "motor-2"]

    # A coordinator refresh now reports only the Living Room motor.
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    # Living Room still present; Bedroom entity + device are both gone.
    assert entity_registry.async_get(LIVING_ROOM_ENTITY) is not None
    assert entity_registry.async_get(BEDROOM_ENTITY) is None
    assert (
        device_registry.async_get_device(
            identifiers={("gaposa", "DEVICE123.motors.motor-2")}
        )
        is None
    )


async def test_entity_removed_when_motor_gone(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa_instance: MagicMock,
) -> None:
    """Cover entity is fully removed when its motor disappears."""
    assert hass.states.get(BEDROOM_ENTITY) is not None

    client, _user = mock_gaposa_instance.clients[0]
    device = client.devices[0]
    device.motors = [m for m in device.motors if m.id != "motor-2"]

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(BEDROOM_ENTITY) is None


async def test_rapid_open_close_replaces_motion_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A second open/close cancels the first motion refresh callback."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    entity = hass.data["entity_components"]["cover"].get_entity(BEDROOM_ENTITY)
    first_cancel = entity._cancel_motion_refresh
    assert first_cancel is not None

    # Issue a second open — should replace the pending refresh.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert entity._cancel_motion_refresh is not first_cancel


async def test_motion_window_collapses_after_delay(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Past MOTION_DELAY, the cover should return to a steady state (not opening/closing)."""
    now = dt_util.utcnow()

    with freeze_time(now):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: BEDROOM_ENTITY},
            blocking=True,
        )

    later = now + timedelta(seconds=MOTION_DELAY + 5)
    with freeze_time(later):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

        state = hass.states.get(BEDROOM_ENTITY).state
        assert state not in (STATE_OPENING, STATE_CLOSING)
