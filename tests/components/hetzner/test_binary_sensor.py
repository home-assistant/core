"""Tests for the Hetzner Cloud binary sensor platform."""

from __future__ import annotations

import pytest

from homeassistant.components.hetzner.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_creation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensors are created for load balancer targets."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entity_entries) == 2

    entity_ids = {entry.entity_id for entry in entity_entries}
    assert "binary_sensor.my_load_balancer_target_web_1_health" in entity_ids
    assert "binary_sensor.my_load_balancer_target_10_0_0_1_health" in entity_ids


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_healthy_state(hass: HomeAssistant) -> None:
    """Test healthy target shows as on."""
    state = hass.states.get("binary_sensor.my_load_balancer_target_web_1_health")
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_unhealthy_state(hass: HomeAssistant) -> None:
    """Test unhealthy target shows as off."""
    state = hass.states.get("binary_sensor.my_load_balancer_target_10_0_0_1_health")
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("init_integration")
async def test_device_registration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test load balancer is registered as a device."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "42")})
    assert device is not None
    assert device.manufacturer == "Hetzner"
    assert device.model == "LB11"
    assert device.name == "my-load-balancer"
