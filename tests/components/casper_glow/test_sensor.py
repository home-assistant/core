"""Test the Casper Glow sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from pycasperglow import BatteryLevel, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

BATTERY_ENTITY_ID = "sensor.jar_battery"


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities match the snapshot."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("battery_level", "expected_state"),
    [
        (BatteryLevel.PCT_75, "75"),
        (BatteryLevel.PCT_50, "50"),
    ],
)
async def test_battery_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    battery_level: BatteryLevel,
    expected_state: str,
) -> None:
    """Test that the battery sensor reflects device state at setup."""
    mock_casper_glow.state = GlowState(battery_level=battery_level)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_battery_state_updated_via_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test battery sensor updates when a device callback fires."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await fire_callbacks(GlowState(battery_level=BatteryLevel.PCT_50))

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "50"
