"""Test the Casper Glow sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from pycasperglow import BatteryLevel, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

BATTERY_ENTITY_ID = "sensor.jar_battery"
DIMMING_END_TIME_ENTITY_ID = "sensor.jar_dimming_end_time"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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


async def test_dimming_end_time_disabled_by_default(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that dimming end time sensor is disabled by default."""
    entry = entity_registry.async_get(DIMMING_END_TIME_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_when_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dimming end time sensor reports a future timestamp when enabled."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=2_520_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    assert state.attributes["device_class"] == SensorDeviceClass.TIMESTAMP


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_unknown_when_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test dimming end time sensor resets to unknown when device turns off."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    # Device turns off — sensor should reset to unknown
    await fire_callbacks(GlowState(is_on=False, dimming_time_remaining_ms=0))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_unknown_when_off_partial_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test dimming end time resets to unknown on an off-only partial callback."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    # Partial callback: only is_on=False, no remaining_ms
    await fire_callbacks(GlowState(is_on=False))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_unknown_when_paused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test dimming end time sensor resets to unknown when dimming is paused."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    # Dimming paused — remaining_ms stays constant but end time is meaningless
    await fire_callbacks(GlowState(is_paused=True, dimming_time_remaining_ms=900_000))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Dimming resumed — end time should be projected again
    await fire_callbacks(GlowState(is_paused=False, dimming_time_remaining_ms=900_000))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_unknown_when_paused_partial_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test dimming end time resets to unknown on a pause-only partial callback."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN

    # Partial callback: only is_paused, no remaining_ms
    await fire_callbacks(GlowState(is_paused=True))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_variance_reset_on_resume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that pause/resume resets the variance filter for a fresh timestamp."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    first_value = state.state

    # Pause, then resume with 10 seconds less remaining. Without the
    # variance reset, ignore_variance would return the cached pre-pause
    # value since 10 seconds is within the 90-second deadband.
    await fire_callbacks(GlowState(is_paused=True, dimming_time_remaining_ms=900_000))
    await fire_callbacks(GlowState(is_paused=False, dimming_time_remaining_ms=890_000))

    state = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    assert state.state != first_value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_jitter_suppression(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that small BLE jitter does not change the projected end time."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state1 = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state1 is not None
    first_value = state1.state

    # Simulate a small jitter — 10 seconds less (within 90-second deadband)
    await fire_callbacks(GlowState(dimming_time_remaining_ms=890_000))

    state2 = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state2 is not None
    assert state2.state == first_value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dimming_end_time_updates_on_significant_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that a large change in remaining time updates the projected end time."""
    mock_casper_glow.state = GlowState(dimming_time_remaining_ms=900_000)
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state1 = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state1 is not None
    first_value = state1.state

    # Simulate a significant change — 10 minutes less (outside 90-second deadband)
    await fire_callbacks(GlowState(dimming_time_remaining_ms=300_000))

    state2 = hass.states.get(DIMMING_END_TIME_ENTITY_ID)
    assert state2 is not None
    assert state2.state != first_value
