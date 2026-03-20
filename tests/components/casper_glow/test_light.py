"""Test the Casper Glow light platform."""

from unittest.mock import MagicMock, patch

from pycasperglow import CasperGlowError, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.casper_glow.const import DEFAULT_DIMMING_TIME_MINUTES
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
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
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "light.jar"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all light entities match the snapshot."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test turning on the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_casper_glow.turn_on.assert_called_once_with()


async def test_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test turning off the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_casper_glow.turn_off.assert_called_once_with()


async def test_state_update_via_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that the entity updates state when the device fires a callback."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    callback = mock_casper_glow.register_callback.call_args[0][0]

    callback(GlowState(is_on=True))
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    callback(GlowState(is_on=False))
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_color_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the light reports BRIGHTNESS color mode."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # color_mode is None until the device reports its state
    assert state.attributes.get(ATTR_COLOR_MODE) is None
    # supported_color_modes is a static class attribute, always present
    assert ColorMode.BRIGHTNESS in state.attributes["supported_color_modes"]


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test turning on the light with brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )

    mock_casper_glow.turn_on.assert_called_once_with()
    mock_casper_glow.set_brightness_and_dimming_time.assert_called_once_with(
        100, DEFAULT_DIMMING_TIME_MINUTES
    )


@pytest.mark.parametrize(
    ("ha_brightness", "device_pct"),
    [
        (1, 60),
        (51, 60),
        (102, 70),
        (153, 80),
        (204, 90),
        (255, 100),
    ],
)
async def test_brightness_snap_to_nearest(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    ha_brightness: int,
    device_pct: int,
) -> None:
    """Test that brightness values map correctly to device percentages."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: ha_brightness},
        blocking=True,
    )

    mock_casper_glow.turn_on.assert_called_once_with()
    mock_casper_glow.set_brightness_and_dimming_time.assert_called_once_with(
        device_pct, DEFAULT_DIMMING_TIME_MINUTES
    )


async def test_brightness_update_via_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that brightness updates via device callback."""
    callback = mock_casper_glow.register_callback.call_args[0][0]
    callback(GlowState(is_on=True, brightness_level=80))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 153


async def test_turn_on_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that a turn on error raises HomeAssistantError without marking entity unavailable."""
    mock_casper_glow.turn_on.side_effect = CasperGlowError("Connection failed")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_turn_off_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that a turn off error raises HomeAssistantError."""
    mock_casper_glow.turn_off.side_effect = CasperGlowError("Connection failed")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_state_update_via_callback_after_command_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that device callbacks correctly update state even after a command failure."""
    mock_casper_glow.turn_on.side_effect = CasperGlowError("Connection failed")

    # Fail a command — entity remains in last known state (unknown), not unavailable
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Device sends a push state update — entity reflects true device state
    callback = mock_casper_glow.register_callback.call_args[0][0]
    callback(GlowState(is_on=True))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
