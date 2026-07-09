"""Tests for the Bosch SHC cover platform."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from boschshcpy import SHCShutterControl
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

STOPPED = SHCShutterControl.ShutterControlService.State.STOPPED
OPENING = SHCShutterControl.ShutterControlService.State.OPENING
CLOSING = SHCShutterControl.ShutterControlService.State.CLOSING

# Every device_helper bucket bosch_shc's platforms iterate over, defaulted to
# empty so a full component setup only ever creates the cover entities under
# test here, regardless of what other platforms look for.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "shutter_controls",
        "thermostats",
        "wallthermostats",
        "twinguards",
        "smart_plugs",
        "light_switches_bsm",
        "smart_plugs_compact",
        "shutter_contacts",
        "shutter_contacts2",
        "motion_detectors",
        "smoke_detectors",
        "universal_switches",
        "water_leakage_detectors",
        "camera_eyes",
        "camera_360",
    )
}


def _cover_device(
    device_id: str = "hdm:HomeMaticIP:cover1",
    level: float = 0.5,
    operation_state: SHCShutterControl.ShutterControlService.State = STOPPED,
) -> SimpleNamespace:
    """Build a minimal shutter-control device double."""
    return SimpleNamespace(
        name="Test Cover",
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


async def _setup_cover_integration(
    hass: HomeAssistant, devices: list[SimpleNamespace]
) -> MockConfigEntry:
    """Set up bosch_shc with the given shutter_controls devices, via a mocked session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    mock_session.information.unique_id = "test-mac"
    mock_session.information.updateState.name = "UP_TO_DATE"
    mock_session.information.version = "2.0"
    mock_session.device_helper = SimpleNamespace(
        **{**_EMPTY_DEVICE_BUCKETS, "shutter_controls": devices}
    )

    with patch(
        "homeassistant.components.bosch_shc.SHCSession", return_value=mock_session
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_setup_creates_one_entity_per_shutter_control(
    hass: HomeAssistant,
) -> None:
    """Each shutter_controls device yields one cover entity."""
    device1 = _cover_device("hdm:HomeMaticIP:cover1", level=0.5)
    device2 = _cover_device("hdm:HomeMaticIP:cover2", level=1.0)

    await _setup_cover_integration(hass, [device1, device2])

    states = hass.states.async_all(COVER_DOMAIN)
    assert len(states) == 2
    state1 = hass.states.get("cover.test_cover")
    assert state1 is not None
    assert state1.attributes["current_position"] == 50
    assert state1.attributes["device_class"] == CoverDeviceClass.SHUTTER
    assert state1.attributes["supported_features"] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No shutter_controls devices means no cover entities are created."""
    await _setup_cover_integration(hass, [])

    assert hass.states.async_all(COVER_DOMAIN) == []


async def test_current_cover_position_open(hass: HomeAssistant) -> None:
    """A fully-open shutter (level=1.0) reports state open and position 100."""
    await _setup_cover_integration(hass, [_cover_device(level=1.0)])

    state = hass.states.get("cover.test_cover")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 100


async def test_current_cover_position_closed(hass: HomeAssistant) -> None:
    """A fully-closed shutter (level=0.0) reports state closed and position 0."""
    await _setup_cover_integration(hass, [_cover_device(level=0.0)])

    state = hass.states.get("cover.test_cover")
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 0


async def test_current_cover_position_partially_open(hass: HomeAssistant) -> None:
    """A partially-open shutter is reported as open, not closed."""
    await _setup_cover_integration(hass, [_cover_device(level=0.1)])

    state = hass.states.get("cover.test_cover")
    assert state is not None
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
    await _setup_cover_integration(
        hass, [_cover_device(level=0.5, operation_state=operation_state)]
    )

    state = hass.states.get("cover.test_cover")
    assert state is not None
    assert state.state == expected_cover_state


async def test_stop_cover_calls_device_stop(hass: HomeAssistant) -> None:
    """The stop_cover service delegates to the device's stop()."""
    device = _cover_device()
    await _setup_cover_integration(hass, [device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )

    device.stop.assert_called_once_with()


async def test_open_cover_sets_level_to_full(hass: HomeAssistant) -> None:
    """The open_cover service writes level=1.0 (fully open)."""
    device = _cover_device(level=0.0)
    await _setup_cover_integration(hass, [device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )

    assert device.level == 1.0


async def test_close_cover_sets_level_to_zero(hass: HomeAssistant) -> None:
    """The close_cover service writes level=0.0 (fully closed)."""
    device = _cover_device(level=1.0)
    await _setup_cover_integration(hass, [device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
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
    await _setup_cover_integration(hass, [device])

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_cover", ATTR_POSITION: position},
        blocking=True,
    )

    assert device.level == pytest.approx(expected_level)
