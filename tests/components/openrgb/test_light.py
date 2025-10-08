"""Tests for the OpenRGB light platform."""

from collections.abc import Generator
import copy
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from openrgb.utils import OpenRGBDisconnected, RGBColor
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.components.openrgb.const import (
    DEFAULT_COLOR,
    DOMAIN,
    OFF_COLOR,
    SCAN_INTERVAL,
    OpenRGBMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.openrgb.PLATFORMS",
        [Platform.LIGHT],
    ):
        yield


# Test basic entity setup and configuration
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entities are correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                f"{mock_config_entry.entry_id}||DRAM||ENE||ENE SMBus Device||none||I2C: PIIX4, address 0x70",
            )
        }
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # Filter out the server device
    entity_entries = [e for e in entity_entries if e.device_id == device_entry.id]
    assert len(entity_entries) == 1
    assert entity_entries[0].device_id == device_entry.id


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_light_with_black_leds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test light state when all LEDs are black (off by color)."""
    # Set all LEDs to black
    mock_openrgb_device.colors = [RGBColor(*OFF_COLOR), RGBColor(*OFF_COLOR)]
    mock_openrgb_device.active_mode = 0  # Direct mode (supports colors)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light is off by color
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_RGB_COLOR) is None
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_light_with_one_non_black_led(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test light state when one LED is non-black among black LEDs (on by color)."""
    # Set one LED to red, others to black
    mock_openrgb_device.colors = [RGBColor(*OFF_COLOR), RGBColor(255, 0, 0)]
    mock_openrgb_device.active_mode = 0  # Direct mode (supports colors)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light is on with the non-black LED color
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.RGB
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.RGB]
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 0, 0)
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_light_with_non_color_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test light state with a mode that doesn't support colors."""
    # Set to Rainbow mode (doesn't support colors)
    mock_openrgb_device.active_mode = 6

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light is on with ON/OFF mode
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == LightEntityFeature.EFFECT
    assert state.attributes.get(ATTR_EFFECT) == "Rainbow"
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.ONOFF
    assert state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) == [ColorMode.ONOFF]
    assert state.attributes.get(ATTR_RGB_COLOR) is None
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_light_with_no_effects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test light with a device that has no effects."""
    # Keep only no-effect modes in the device
    mock_openrgb_device.modes = [
        mode
        for mode in mock_openrgb_device.modes
        if mode.name in {OpenRGBMode.OFF, OpenRGBMode.DIRECT, OpenRGBMode.STATIC}
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light entity doesn't have EFFECT feature
    state = hass.states.get("light.ene_dram")
    assert state

    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    assert state.attributes.get(ATTR_EFFECT) is None

    # Verify the light is still functional (can be turned on/off)
    assert state.state == STATE_ON


# Test basic turn on/off functionality
@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light."""
    # Initialize device in Off mode
    mock_openrgb_device.active_mode = 1

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light is initially off
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Verify that set_mode was called to restore to Direct mode (preferred over Static)
    mock_openrgb_device.set_mode.assert_called_once_with(OpenRGBMode.DIRECT)
    # And set_color was called with default color
    mock_openrgb_device.set_color.assert_called_once_with(
        RGBColor(*DEFAULT_COLOR), True
    )


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_light_with_color(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light with color."""
    # Start with color Red at half brightness
    mock_openrgb_device.colors = [RGBColor(128, 0, 0), RGBColor(128, 0, 0)]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 0, 0)  # Red
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ene_dram",
            ATTR_RGB_COLOR: (0, 255, 0),  # Green
        },
        blocking=True,
    )

    # Check that set_color was called with Green color scaled with half brightness
    mock_openrgb_device.set_color.assert_called_once_with(RGBColor(0, 128, 0), True)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_light_with_brightness(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the light with brightness."""
    # Start with color Red at full brightness
    mock_openrgb_device.colors = [RGBColor(255, 0, 0), RGBColor(255, 0, 0)]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 0, 0)  # Red
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ene_dram",
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )

    # Check that set_color was called with Red color scaled with half brightness
    mock_openrgb_device.set_color.assert_called_once_with(RGBColor(128, 0, 0), True)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_effect(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light with effect."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ene_dram",
            ATTR_EFFECT: "Rainbow",
        },
        blocking=True,
    )

    mock_openrgb_device.set_mode.assert_called_once_with("Rainbow")


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_effect_off(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light with effect Off."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ene_dram",
            ATTR_EFFECT: EFFECT_OFF,
        },
        blocking=True,
    )

    # Should switch to Direct mode (preferred over Static)
    mock_openrgb_device.set_mode.assert_called_once_with(OpenRGBMode.DIRECT)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_restores_previous_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning on after off restores previous brightness, color, and mode."""
    # Start with device in Static mode with blue color
    mock_openrgb_device.active_mode = 2
    mock_openrgb_device.colors = [RGBColor(0, 0, 128), RGBColor(0, 0, 128)]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Now device is in Off mode
    mock_openrgb_device.active_mode = 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters - should restore previous mode and values
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Should restore to Static mode (previous mode) even though Direct is preferred
    mock_openrgb_device.set_mode.assert_called_once_with(OpenRGBMode.STATIC)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_previous_values_updated_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that previous values are updated when device state changes externally."""
    # Start with device in Direct mode with red color at full brightness
    mock_openrgb_device.active_mode = 0
    mock_openrgb_device.colors = [RGBColor(255, 0, 0), RGBColor(255, 0, 0)]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 0, 0)  # Red
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255
    assert state.attributes.get(ATTR_EFFECT) == EFFECT_OFF  # Direct mode

    # Simulate external change to green at 50% brightness in Breathing mode
    # (e.g., via the OpenRGB application)
    mock_openrgb_device.active_mode = 3  # Breathing mode
    mock_openrgb_device.colors = [RGBColor(0, 128, 0), RGBColor(0, 128, 0)]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify new state
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_RGB_COLOR) == (0, 255, 0)  # Green
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128  # 50% brightness
    assert state.attributes.get(ATTR_EFFECT) == "Breathing"

    # Simulate external change to Off mode
    mock_openrgb_device.active_mode = 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify light is off
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters - should restore most recent state (green, 50%, Breathing)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    mock_openrgb_device.set_mode.assert_called_once_with("Breathing")
    mock_openrgb_device.set_color.assert_called_once_with(RGBColor(0, 128, 0), True)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_restores_rainbow_after_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning on after off restores Rainbow effect (non-color mode)."""
    # Start with device in Rainbow mode (doesn't support colors)
    mock_openrgb_device.active_mode = 6

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state - Rainbow mode active
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_EFFECT) == "Rainbow"

    # Turn off the light by switching to Off mode
    mock_openrgb_device.active_mode = 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify light is off
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters - should restore Rainbow mode
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Should restore to Rainbow mode (previous mode)
    mock_openrgb_device.set_mode.assert_called_once_with("Rainbow")
    # set_color should NOT be called since Rainbow doesn't support colors
    mock_openrgb_device.set_color.assert_not_called()


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_on_restores_rainbow_after_off_by_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning on after off by color restores Rainbow effect (non-color mode)."""
    # Start with device in Rainbow mode (doesn't support colors)
    mock_openrgb_device.active_mode = 6

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state - Rainbow mode active
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_EFFECT) == "Rainbow"

    # Turn off the light by setting all LEDs to black in Direct mode
    mock_openrgb_device.active_mode = 0  # Direct mode
    mock_openrgb_device.colors = [RGBColor(*OFF_COLOR), RGBColor(*OFF_COLOR)]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify light is off
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters - should restore Rainbow mode, not Direct
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Should restore to Rainbow mode (previous mode), not Direct
    mock_openrgb_device.set_mode.assert_called_once_with("Rainbow")
    # set_color should NOT be called since Rainbow doesn't support colors
    mock_openrgb_device.set_color.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_light(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning off the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Device supports "Off" mode
    mock_openrgb_device.set_mode.assert_called_once_with(OpenRGBMode.OFF)


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_turn_off_light_without_off_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning off a light that doesn't support Off mode."""
    # Modify the device to not have Off mode
    mock_openrgb_device.modes = [
        mode_data
        for mode_data in mock_openrgb_device.modes
        if mode_data.name != OpenRGBMode.OFF
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify light is initially on
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Turn off the light
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.ene_dram"},
        blocking=True,
    )

    # Device should have set_color called with black/off color instead
    mock_openrgb_device.set_color.assert_called_once_with(RGBColor(*OFF_COLOR), True)


# Test error handling
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [OpenRGBDisconnected(), ValueError("Invalid color")],
)
async def test_turn_on_light_with_color_exceptions(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
    exception: Exception,
) -> None:
    """Test turning on the light with exceptions when setting color."""
    mock_openrgb_device.set_color.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.ene_dram",
                ATTR_RGB_COLOR: (0, 255, 0),
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [OpenRGBDisconnected(), ValueError("Invalid mode")],
)
async def test_turn_on_light_with_mode_exceptions(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
    exception: Exception,
) -> None:
    """Test turning on the light with exceptions when setting mode."""
    mock_openrgb_device.set_mode.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.ene_dram",
                ATTR_EFFECT: "Rainbow",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_unsupported_effect(
    hass: HomeAssistant,
) -> None:
    """Test turning on the light with an invalid effect."""
    with pytest.raises(
        ServiceValidationError,
        match="Effect `InvalidEffect` is not supported by ENE DRAM",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.ene_dram",
                ATTR_EFFECT: "InvalidEffect",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_color_and_non_color_effect(
    hass: HomeAssistant,
) -> None:
    """Test turning on the light with color/brightness and a non-color effect."""
    with pytest.raises(
        ServiceValidationError,
        match="Effect `Rainbow` does not support color control on ENE DRAM",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.ene_dram",
                ATTR_EFFECT: "Rainbow",
                ATTR_RGB_COLOR: (255, 0, 0),
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_brightness_and_non_color_effect(
    hass: HomeAssistant,
) -> None:
    """Test turning on the light with brightness and a non-color effect."""
    with pytest.raises(
        ServiceValidationError,
        match="Effect `Rainbow` does not support color control on ENE DRAM",
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.ene_dram",
                ATTR_EFFECT: "Rainbow",
                ATTR_BRIGHTNESS: 128,
            },
            blocking=True,
        )


# Test device management
async def test_dynamic_device_addition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new devices are added dynamically."""
    mock_config_entry.add_to_hass(hass)

    # Start with one device
    mock_openrgb_client.devices = [mock_openrgb_device]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Check that one light entity exists
    state = hass.states.get("light.ene_dram")
    assert state

    # Add a second device
    new_device = MagicMock()
    new_device.id = 1  # Different device ID
    new_device.name = "New RGB Device"
    new_device.type = MagicMock()
    new_device.type.name = "KEYBOARD"
    new_device.metadata = MagicMock()
    new_device.metadata.vendor = "New Vendor"
    new_device.metadata.description = "New Keyboard"
    new_device.metadata.serial = "NEW123"
    new_device.metadata.location = "New Location"
    new_device.metadata.version = "2.0.0"
    new_device.active_mode = 0
    new_device.modes = mock_openrgb_device.modes
    new_device.colors = [RGBColor(0, 255, 0)]
    new_device.set_color = MagicMock()
    new_device.set_mode = MagicMock()

    mock_openrgb_client.devices = [mock_openrgb_device, new_device]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Check that second light entity was added
    state = hass.states.get("light.new_rgb_device")
    assert state


@pytest.mark.usefixtures("init_integration")
async def test_light_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test light becomes unavailable when device is unplugged."""
    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_ON

    # Simulate device being momentarily unplugged
    mock_openrgb_client.devices = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("light.ene_dram")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_duplicate_device_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that devices with duplicate names get numeric suffixes."""
    device1 = copy.deepcopy(mock_openrgb_device)
    device1.id = 3  # Should get suffix "1"
    device1.metadata.location = "I2C: PIIX4, address 0x71"

    # Create a true copy of the first device for device2 to ensure they are separate instances
    device2 = copy.deepcopy(mock_openrgb_device)
    device2.id = 4  # Should get suffix "2"
    device2.metadata.location = "I2C: PIIX4, address 0x72"

    mock_openrgb_client.devices = [device1, device2]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The device key format is: entry_id||type||vendor||description||serial||location
    device1_key = f"{mock_config_entry.entry_id}||DRAM||ENE||ENE SMBus Device||none||I2C: PIIX4, address 0x71"
    device2_key = f"{mock_config_entry.entry_id}||DRAM||ENE||ENE SMBus Device||none||I2C: PIIX4, address 0x72"

    # Verify devices exist with correct names (suffix based on device.id position)
    device1_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, device1_key)}
    )
    device2_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, device2_key)}
    )

    assert device1_entry
    assert device2_entry

    # device1 has lower device.id, so it gets suffix "1"
    # device2 has higher device.id, so it gets suffix "2"
    assert device1_entry.name == "ENE DRAM 1"
    assert device2_entry.name == "ENE DRAM 2"
