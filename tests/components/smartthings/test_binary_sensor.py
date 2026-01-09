"""Test for the SmartThings binary_sensor platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(
        hass, entity_registry, snapshot, Platform.BINARY_SENSOR
    )


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.refrigerator_fridge_door").state == STATE_OFF

    await trigger_update(
        hass,
        devices,
        "7db87911-7dce-1cf2-7119-b953432a2f09",
        Capability.CONTACT_SENSOR,
        Attribute.CONTACT,
        "open",
        component="cooler",
    )

    assert hass.states.get("binary_sensor.refrigerator_fridge_door").state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.refrigerator_fridge_door").state == STATE_OFF

    await trigger_health_update(
        hass, devices, "7db87911-7dce-1cf2-7119-b953432a2f09", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("binary_sensor.refrigerator_fridge_door").state
        == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "7db87911-7dce-1cf2-7119-b953432a2f09", HealthStatus.ONLINE
    )

    assert hass.states.get("binary_sensor.refrigerator_fridge_door").state == STATE_OFF


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("binary_sensor.refrigerator_fridge_door").state
        == STATE_UNAVAILABLE
    )
