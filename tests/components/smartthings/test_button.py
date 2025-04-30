"""Test for the SmartThings button platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartthings import Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.smartthings import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities, trigger_health_update

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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.BUTTON)


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_press(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)
    freezer.move_to("2023-10-21")

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.microwave_stop"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2bad3237-4886-e699-1b90-4a51a3d55c8a",
        Capability.OVEN_OPERATING_STATE,
        Command.STOP,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.microwave_stop").state == STATE_UNKNOWN

    await trigger_health_update(
        hass, devices, "2bad3237-4886-e699-1b90-4a51a3d55c8a", HealthStatus.OFFLINE
    )

    assert hass.states.get("button.microwave_stop").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "2bad3237-4886-e699-1b90-4a51a3d55c8a", HealthStatus.ONLINE
    )

    assert hass.states.get("button.microwave_stop").state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["da_ks_microwave_0101x"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("button.microwave_stop").state == STATE_UNAVAILABLE
