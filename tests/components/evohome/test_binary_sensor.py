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
    """Test fault sensors when a zone has no active faults."""

    evo: EvohomeClient = evohome.return_value

    zones_sans_faults = [z for z in evo.tcs.zones if not z.active_faults]
    assert zones_sans_faults

    zone = zones_sans_faults[0]

    # CONNECTIVITY has inverted polarity: no comms fault means is_on (connected)
    state = hass.states.get(
        entity_id(Platform.BINARY_SENSOR, f"{zone.id}_connectivity")
    )
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["faults"] == []

    # BATTERY: no low-battery fault → is_off (normal)
    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_battery"))
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"] == []

    # PROBLEM: no general fault → is_off (OK)
    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_problem"))
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"] == []


@pytest.mark.parametrize("install", ["botched"])
async def test_fault_sensors_on(
    hass: HomeAssistant,
    evohome: MagicMock,
    entity_id: Callable[[Platform, str], str],
) -> None:
    """Test fault sensors when a zone has an active fault."""

    evo: EvohomeClient = evohome.return_value

    # Pick a zone whose active fault is a CommunicationLost.
    zone = next(
        z
        for z in evo.tcs.zones
        if z.active_faults
        and z.active_faults[0]["fault_type"].endswith("CommunicationLost")
    )

    # CONNECTIVITY is inverted: comms fault present → is_off (disconnected)
    state = hass.states.get(
        entity_id(Platform.BINARY_SENSOR, f"{zone.id}_connectivity")
    )
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"][0] == {
        "fault": "temp_zone_actuator_communication_lost",
        "since": datetime(2022, 3, 2, 18, 56, 1, tzinfo=UTC),
    }

    # The same fault must not bleed into the other categories.
    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_battery"))
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"] == []

    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_problem"))
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"] == []

    # And a zone with a LowBattery fault should light up BATTERY only.
    zone = next(
        z
        for z in evo.tcs.zones
        if z.active_faults and z.active_faults[0]["fault_type"].endswith("LowBattery")
    )

    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_battery"))
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["faults"][0]["fault"] == "temp_zone_actuator_low_battery"

    state = hass.states.get(
        entity_id(Platform.BINARY_SENSOR, f"{zone.id}_connectivity")
    )
    assert state is not None
    assert state.state == STATE_ON  # no comms fault → connected
