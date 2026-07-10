"""Tests for the Bosch SHC cover platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from boschshcpy import SHCShutterControl
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import snapshot_platform

STOPPED = SHCShutterControl.ShutterControlService.State.STOPPED
OPENING = SHCShutterControl.ShutterControlService.State.OPENING
CLOSING = SHCShutterControl.ShutterControlService.State.CLOSING

COVER_ENTITY_ID = "cover.cover"


def _cover_device(
    device_id: str = "hdm:HomeMaticIP:cover1",
    level: float = 0.5,
    operation_state: SHCShutterControl.ShutterControlService.State = STOPPED,
) -> SimpleNamespace:
    """Build a minimal shutter-control device double."""
    return SimpleNamespace(
        name="Cover",
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_model="SWD",
        level=level,
        operation_state=operation_state,
        device_services=[],
        manufacturer="Bosch",
        status="AVAILABLE",
        deleted=False,
        stop=MagicMock(),
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
    )


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the cover entities two shutter_controls devices create."""
    entry = await setup_integration(
        hass,
        [Platform.COVER],
        shutter_controls=[
            _cover_device(),
            _cover_device(device_id="hdm:HomeMaticIP:cover2", level=1.0),
        ],
    )

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No shutter_controls devices means no cover entities are created."""
    await setup_integration(hass, [Platform.COVER])

    assert hass.states.async_all(COVER_DOMAIN) == []


async def test_current_cover_position_open(hass: HomeAssistant) -> None:
    """A fully-open shutter (level=1.0) reports state open and position 100."""
    await setup_integration(
        hass, [Platform.COVER], shutter_controls=[_cover_device(level=1.0)]
    )

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 100


async def test_current_cover_position_closed(hass: HomeAssistant) -> None:
    """A fully-closed shutter (level=0.0) reports state closed and position 0."""
    await setup_integration(
        hass, [Platform.COVER], shutter_controls=[_cover_device(level=0.0)]
    )

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 0


async def test_current_cover_position_partially_open(hass: HomeAssistant) -> None:
    """A partially-open shutter is reported as open, not closed."""
    await setup_integration(
        hass, [Platform.COVER], shutter_controls=[_cover_device(level=0.1)]
    )

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 10


@pytest.mark.parametrize(
    ("operation_state", "expected_cover_state"),
    [
        pytest.param(OPENING, CoverState.OPENING, id="opening"),
        pytest.param(CLOSING, CoverState.CLOSING, id="closing"),
    ],
)
async def test_is_opening_and_is_closing(
    hass: HomeAssistant,
    operation_state: SHCShutterControl.ShutterControlService.State,
    expected_cover_state: CoverState,
) -> None:
    """The entity state reflects the device's ShutterControlService.State."""
    await setup_integration(
        hass,
        [Platform.COVER],
        shutter_controls=[_cover_device(level=0.5, operation_state=operation_state)],
    )

    state = hass.states.get(COVER_ENTITY_ID)
    assert state.state == expected_cover_state


async def test_stop_cover_calls_device_stop(hass: HomeAssistant) -> None:
    """The stop_cover service delegates to the device's stop()."""
    device = _cover_device()
    await setup_integration(hass, [Platform.COVER], shutter_controls=[device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    device.stop.assert_called_once_with()


async def test_open_cover_sets_level_to_full(hass: HomeAssistant) -> None:
    """The open_cover service writes level=1.0 (fully open)."""
    device = _cover_device(level=0.0)
    await setup_integration(hass, [Platform.COVER], shutter_controls=[device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert device.level == 1.0


async def test_close_cover_sets_level_to_zero(hass: HomeAssistant) -> None:
    """The close_cover service writes level=0.0 (fully closed)."""
    device = _cover_device(level=1.0)
    await setup_integration(hass, [Platform.COVER], shutter_controls=[device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert device.level == 0.0


@pytest.mark.parametrize(
    ("position", "expected_level"),
    [
        pytest.param(0, 0.0, id="closed"),
        pytest.param(50, 0.5, id="half_open"),
        pytest.param(100, 1.0, id="fully_open"),
        pytest.param(42, 0.42, id="arbitrary"),
    ],
)
async def test_set_cover_position(
    hass: HomeAssistant, position: int, expected_level: float
) -> None:
    """The set_cover_position service converts 0..100 position back to a 0..1 level."""
    device = _cover_device()
    await setup_integration(hass, [Platform.COVER], shutter_controls=[device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID, ATTR_POSITION: position},
        blocking=True,
    )

    assert device.level == pytest.approx(expected_level)
