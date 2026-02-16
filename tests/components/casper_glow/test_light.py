"""Test the Casper Glow light platform."""

from unittest.mock import AsyncMock, patch

from pycasperglow import CasperGlowError, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.casper_glow.const import DEFAULT_DIMMING_TIME_MINUTES
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_MODE, ColorMode
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import CASPER_GLOW_DISCOVERY_INFO, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "light.jar"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all light entities match the snapshot."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test turning on the light."""
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ) as mock_turn_on:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_turn_on.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_turn_off(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test turning off the light."""
    # First turn on
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    # Then turn off
    with patch(
        "pycasperglow.CasperGlow.turn_off",
    ) as mock_turn_off:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_turn_off.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_update_via_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the entity updates state when the device fires a callback."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Simulate device pushing a state update
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Push state off
    device._state = GlowState(is_on=False)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_color_mode(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test that the light reports BRIGHTNESS color mode."""
    # Turn on the light to verify color_mode is set
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.BRIGHTNESS


async def test_turn_on_with_brightness(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test turning on the light with brightness."""
    with (
        patch("pycasperglow.CasperGlow.turn_on") as mock_turn_on,
        patch(
            "pycasperglow.CasperGlow.set_brightness_and_dimming_time",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )

    mock_turn_on.assert_called_once_with()
    mock_set.assert_called_once_with(100, DEFAULT_DIMMING_TIME_MINUTES)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255


@pytest.mark.parametrize(
    ("ha_brightness", "device_pct", "expected_ha_brightness"),
    [
        (1, 60, 1),
        (64, 70, 64),
        (128, 80, 128),
        (192, 90, 192),
        (255, 100, 255),
    ],
)
async def test_brightness_snap_to_nearest(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ha_brightness: int,
    device_pct: int,
    expected_ha_brightness: int,
) -> None:
    """Test that brightness values map correctly to device percentages and back."""
    with (
        patch("pycasperglow.CasperGlow.turn_on") as mock_turn_on,
        patch(
            "pycasperglow.CasperGlow.set_brightness_and_dimming_time",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: ha_brightness},
            blocking=True,
        )

    mock_turn_on.assert_called_once_with()
    mock_set.assert_called_once_with(device_pct, DEFAULT_DIMMING_TIME_MINUTES)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected_ha_brightness


async def test_brightness_update_via_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that brightness updates via device callback."""
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True, brightness_level=80)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128


async def test_turn_on_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a turn on error raises HomeAssistantError without marking entity unavailable."""
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_turn_off_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a turn off error raises HomeAssistantError and leaves the light on."""
    # First turn on
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    with (
        patch(
            "pycasperglow.CasperGlow.turn_off",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info is correctly populated."""
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, CASPER_GLOW_DISCOVERY_INFO.address)}
    )
    assert device is not None
    assert device.manufacturer == "Casper"
    assert device.model == "G01"


async def test_state_update_via_callback_after_command_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that device callbacks correctly update state even after a command failure."""
    # Fail a command — entity remains in last known state (unknown), not unavailable
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Device sends a push state update — entity reflects true device state
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
