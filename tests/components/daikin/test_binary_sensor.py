"""Tests for Daikin binary sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.daikin.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, async_setup_daikin

DEMAND_CONTROL_DATA = {
    "en_demand": "1",
    "dmd_mode": "0",
    "max_pow": "50",
    "scdl_per_day": "4",
}


def _demand_control_entity_id(
    entity_registry: er.EntityRegistry, zone_device: ZoneDevice
) -> str | None:
    """Return the demand control sensor entity id."""
    return entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{zone_device.mac}-demand_control"
    )


async def test_demand_control_sensor_snapshot(
    hass: HomeAssistant,
    zone_device: ZoneDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the demand control sensor state with a snapshot."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control = MagicMock(return_value=DEMAND_CONTROL_DATA)

    await async_setup_daikin(hass, zone_device)

    entity_id = _demand_control_entity_id(entity_registry, zone_device)
    assert entity_id is not None

    assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("en_demand", "expected_state"),
    [
        pytest.param("1", STATE_ON, id="on"),
        pytest.param("0", STATE_OFF, id="off"),
    ],
)
async def test_demand_control_sensor_state(
    hass: HomeAssistant,
    zone_device: ZoneDevice,
    entity_registry: er.EntityRegistry,
    en_demand: str,
    expected_state: str,
) -> None:
    """Test the demand control sensor reports the enabled state."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control = MagicMock(
        return_value={**DEMAND_CONTROL_DATA, "en_demand": en_demand}
    )

    await async_setup_daikin(hass, zone_device)

    entity_id = _demand_control_entity_id(entity_registry, zone_device)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == expected_state


async def test_demand_control_sensor_schedule_mode_excludes_max_pow(
    hass: HomeAssistant,
    zone_device: ZoneDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test max_pow is excluded from attributes in schedule mode."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control = MagicMock(
        return_value={**DEMAND_CONTROL_DATA, "mode": "1"}
    )

    await async_setup_daikin(hass, zone_device)

    entity_id = _demand_control_entity_id(entity_registry, zone_device)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert "max_pow" not in state.attributes


async def test_demand_control_sensor_not_created_unsupported(
    hass: HomeAssistant,
    zone_device: ZoneDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the demand control sensor is not created on unsupported devices."""
    await async_setup_daikin(hass, zone_device)

    assert _demand_control_entity_id(entity_registry, zone_device) is None
