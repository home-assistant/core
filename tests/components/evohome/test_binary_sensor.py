"""The tests for the binary_sensor platform of evohome."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import MagicMock

from evohomeasync2 import EvohomeClient
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
@pytest.mark.usefixtures("evohome")
async def test_setup_platform(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that binary_sensor entities are created after setup of Evohome."""

    binary_sensor_states = hass.states.async_all(BINARY_SENSOR_DOMAIN)
    assert binary_sensor_states

    for x in binary_sensor_states:
        assert x == snapshot(name=f"{x.entity_id}-state")


@pytest.mark.parametrize("install", ["default"])
async def test_fault_sensors_off(
    hass: HomeAssistant,
    evohome: MagicMock,
    entity_id: Callable[[Platform, str], str],
) -> None:
    """Test fault sensors when system has no active system faults."""

    evo: EvohomeClient = evohome.return_value

    zones_with_faults = [z for z in evo.tcs.zones if z.active_faults]
    zones_sans_faults = [z for z in evo.tcs.zones if not z.active_faults]

    assert zones_with_faults == []
    assert zones_sans_faults

    zone_sans_fault = zones_sans_faults[0]
    state_sans_fault = hass.states.get(
        entity_id(Platform.BINARY_SENSOR, f"{zone_sans_fault.id}_faults")
    )
    assert state_sans_fault is not None
    assert state_sans_fault.state == STATE_OFF

    assert state_sans_fault.attributes["faults"] == []


@pytest.mark.parametrize("install", ["botched"])
async def test_fault_sensors_on(
    hass: HomeAssistant,
    evohome: MagicMock,
    entity_id: Callable[[Platform, str], str],
) -> None:
    """Test fault sensors when system has active system faults."""

    evo: EvohomeClient = evohome.return_value

    zones_with_faults = [z for z in evo.tcs.zones if z.active_faults]
    zones_sans_faults = [z for z in evo.tcs.zones if not z.active_faults]

    assert zones_with_faults
    assert zones_sans_faults

    zone_with_fault = zones_with_faults[0]
    state_with_fault = hass.states.get(
        entity_id(Platform.BINARY_SENSOR, f"{zone_with_fault.id}_faults")
    )
    assert state_with_fault is not None
    assert state_with_fault.state == STATE_ON

    assert state_with_fault.attributes["faults"][0] == {
        "fault": "temp_zone_actuator_communication_lost",
        "since": datetime(2022, 3, 2, 18, 56, 1, tzinfo=UTC),
    }
