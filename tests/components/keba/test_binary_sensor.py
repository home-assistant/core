"""Tests for the KEBA charging station binary sensors."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import snapshot_keba_platform
from .conftest import POLL_INTERVAL, async_advance


async def test_binary_sensors(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor entities, their unique IDs and states."""
    snapshot_keba_platform(hass, entity_registry, snapshot, Platform.BINARY_SENSOR)


@pytest.mark.parametrize(
    ("plugged", "wallbox", "locked", "ev", "expected"),
    [
        (False, False, False, False, STATE_OFF),
        (False, True, False, False, STATE_OFF),
        (True, True, False, True, STATE_ON),
        (True, True, True, True, STATE_ON),
    ],
)
async def test_plug_state(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    plugged: bool,
    wallbox: bool,
    locked: bool,
    ev: bool,
    expected: str,
) -> None:
    """Test the plug sensor follows the library's plug flags."""
    keba_data.update(
        {
            "Plug_plugged": plugged,
            "Plug_wallbox": wallbox,
            "Plug_locked": locked,
            "Plug_EV": ev,
        }
    )

    await async_advance(hass, freezer, POLL_INTERVAL)

    state = hass.states.get("binary_sensor.keba_p30_plug")
    assert state.state == expected
    assert state.attributes["plugged_on_wallbox"] is wallbox
    assert state.attributes["plug_locked"] is locked
    assert state.attributes["plugged_on_EV"] is ev


@pytest.mark.parametrize(
    ("charging", "details", "expected"),
    [
        (False, "ready for charging", STATE_OFF),
        (True, "charging", STATE_ON),
        (False, "error", STATE_OFF),
    ],
)
async def test_charging_state(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    charging: bool,
    details: str,
    expected: str,
) -> None:
    """Test the charging state sensor and its status attribute."""
    keba_data.update({"State_on": charging, "State_details": details})

    await async_advance(hass, freezer, POLL_INTERVAL)

    state = hass.states.get("binary_sensor.keba_p30_charging_state")
    assert state.state == expected
    assert state.attributes["status"] == details


@pytest.mark.parametrize(
    ("failsafe_on", "expected"),
    [(False, STATE_ON), (True, STATE_OFF)],
)
async def test_failsafe_mode_is_inverted(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    failsafe_on: bool,
    expected: str,
) -> None:
    """Test the failsafe sensor is on (unsafe) while failsafe is off."""
    keba_data["FS_on"] = failsafe_on

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get("binary_sensor.keba_p30_failsafe_mode").state == expected
