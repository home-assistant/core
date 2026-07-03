"""The tests for the binary_sensor platform of evohome."""

from __future__ import annotations

from collections.abc import Callable
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
    """Test that battery binary_sensor entities are created after setup of Evohome."""

    binary_sensor_states = hass.states.async_all(BINARY_SENSOR_DOMAIN)
    assert binary_sensor_states

    for x in binary_sensor_states:
        assert x == snapshot(name=f"{x.entity_id}-state")


@pytest.mark.parametrize("install", ["default"])
async def test_battery_sensor_off(
    hass: HomeAssistant,
    evohome: MagicMock,
    entity_id: Callable[[Platform, str], str],
) -> None:
    """Test battery sensor reports off (normal) when a zone has no active faults."""

    evo: EvohomeClient = evohome.return_value

    zone = next(z for z in evo.tcs.zones if not z.active_faults)

    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_battery"))
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize("install", ["botched"])
async def test_battery_sensor_on(
    hass: HomeAssistant,
    evohome: MagicMock,
    entity_id: Callable[[Platform, str], str],
) -> None:
    """Test battery sensor reports on when a zone has an active LowBattery fault."""

    evo: EvohomeClient = evohome.return_value

    zone = next(
        z
        for z in evo.tcs.zones
        if any(str(f["fault_type"]).endswith("low_battery") for f in z.active_faults)
    )

    state = hass.states.get(entity_id(Platform.BINARY_SENSOR, f"{zone.id}_battery"))
    assert state is not None
    assert state.state == STATE_ON
