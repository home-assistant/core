"""Tests for Daikin demand control sensor."""

import pytest

from homeassistant.components.daikin.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ZoneDevice, async_setup_daikin


def _demand_control_entity_id(
    entity_registry: er.EntityRegistry, mac: str
) -> str | None:
    """Return the demand control sensor entity ID."""
    return entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{mac}-demand_control",
    )


@pytest.mark.parametrize(
    ("demand_control", "expected_state", "expected_attributes"),
    [
        pytest.param(
            {"en_demand": "1", "mode": "0", "max_pow": "50"},
            "manual",
            {"armed_mode": "manual", "max_pow": 50},
            id="enabled-manual",
        ),
        pytest.param(
            {"en_demand": "0", "mode": "2", "max_pow": "50"},
            "off",
            {"armed_mode": "auto"},
            id="disabled-auto",
        ),
        pytest.param(
            {"en_demand": "1", "mode": "2", "max_pow": "50"},
            "auto",
            {"armed_mode": "auto"},
            id="enabled-auto",
        ),
        pytest.param(
            {"en_demand": "0", "mode": "0", "max_pow": "50"},
            "off",
            {"armed_mode": "manual", "max_pow": 50},
            id="disabled-manual",
        ),
        pytest.param(
            {"en_demand": "0", "mode": "1", "max_pow": "50"},
            "off",
            {},
            id="unsupported-mode",
        ),
    ],
)
async def test_demand_control_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    demand_control: dict[str, str],
    expected_state: str,
    expected_attributes: dict[str, str | int],
) -> None:
    """Test demand control sensor state and attributes."""
    zone_device.support_demand_control = True
    zone_device.get_demand_control.return_value = demand_control

    await async_setup_daikin(hass, zone_device)
    entity_id = _demand_control_entity_id(entity_registry, zone_device.mac)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert {
        key: state.attributes[key]
        for key in ("armed_mode", "max_pow")
        if key in state.attributes
    } == expected_attributes
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == ["off", "auto", "manual"]


async def test_demand_control_sensor_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Do not create a demand control sensor when unsupported."""
    await async_setup_daikin(hass, zone_device)

    assert _demand_control_entity_id(entity_registry, zone_device.mac) is None
