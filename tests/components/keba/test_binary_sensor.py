"""Tests for the KEBA charging station binary sensors."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import snapshot_keba_platform
from .conftest import POLL_INTERVAL, FakeKebaStation, async_advance


async def test_binary_sensors(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor entities, their unique IDs and states."""
    snapshot_keba_platform(hass, entity_registry, snapshot, Platform.BINARY_SENSOR)


@pytest.mark.parametrize(
    ("plug", "plugged", "plug_locked"),
    [
        (0, STATE_OFF, False),
        (1, STATE_OFF, False),
        # 3 is "plugged on the station and locked"; the library's
        # `plug_state == 3 | plug_state == 7` parses as a chained comparison
        # and only matches 7.
        (3, STATE_OFF, False),
        (5, STATE_ON, False),
        (7, STATE_ON, True),
    ],
)
async def test_plug_state(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    plug: int,
    plugged: str,
    plug_locked: bool,
) -> None:
    """Test the plug sensor and its plug_locked attribute for each plug state."""
    setup_keba.push("2", Plug=plug)

    await async_advance(hass, freezer, POLL_INTERVAL)

    state = hass.states.get("binary_sensor.keba_p30_plug")
    assert state.state == plugged
    assert state.attributes["plug_locked"] is plug_locked


@pytest.mark.parametrize(
    ("charging_state", "expected", "details"),
    [
        (2, STATE_OFF, "ready for charging"),
        (3, STATE_ON, "charging"),
        (4, STATE_OFF, "error"),
        (9, STATE_OFF, "State undefined"),
    ],
)
async def test_charging_state(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    charging_state: int,
    expected: str,
    details: str,
) -> None:
    """Test the charging state sensor and its status attribute."""
    setup_keba.push("2", State=charging_state)

    await async_advance(hass, freezer, POLL_INTERVAL)

    state = hass.states.get("binary_sensor.keba_p30_charging_state")
    assert state.state == expected
    assert state.attributes["status"] == details


@pytest.mark.parametrize(
    ("timeout", "expected"),
    [(0, STATE_ON), (30, STATE_OFF)],
)
async def test_failsafe_mode_is_inverted(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    freezer: FrozenDateTimeFactory,
    timeout: int,
    expected: str,
) -> None:
    """Test the failsafe sensor is on (unsafe) while failsafe is off."""
    setup_keba.push("2", **{"Tmo FS": timeout})

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get("binary_sensor.keba_p30_failsafe_mode").state == expected
