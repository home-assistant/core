"""Test for the SmartThings number platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_set_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.washer_rinse_cycles", ATTR_VALUE: 3},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Command.SET_WASHER_RINSE_CYCLES,
        MAIN,
        argument="3",
    )


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.washer_rinse_cycles").state == "2"

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Attribute.WASHER_RINSE_CYCLES,
        "3",
    )

    assert hass.states.get("number.washer_rinse_cycles").state == "3"


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.washer_rinse_cycles").state == "2"

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.OFFLINE
    )

    assert hass.states.get("number.washer_rinse_cycles").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "f984b91d-f250-9d42-3436-33f09a422a47", HealthStatus.ONLINE
    )

    assert hass.states.get("number.washer_rinse_cycles").state == "2"
