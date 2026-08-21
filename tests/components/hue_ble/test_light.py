"""Hue BLE light tests."""

from unittest.mock import AsyncMock

from HueBLE import EffectType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hue_ble.const import EFFECT_SPEED
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_XY_COLOR,
    DOMAIN,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.hue_ble import TEST_DEVICE_NAME


async def test_light(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test light entity setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_light_control_basic(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on/off and brightness control."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = f"light.{TEST_DEVICE_NAME.lower().replace(' ', '_')}"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 100

    await hass.services.async_call(
        DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert not mock_light.power_state

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 50},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 50
    assert mock_light.power_state

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 200},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 200
    assert mock_light.power_state


async def test_light_control_color_temp(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color temperature control."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = f"light.{TEST_DEVICE_NAME.lower().replace(' ', '_')}"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 4000
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert mock_light.colour_temp == 250

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 3003
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert mock_light.colour_temp == 333


async def test_light_control_color_xy(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color (xy) control."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = f"light.{TEST_DEVICE_NAME.lower().replace(' ', '_')}"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_XY_COLOR] == (0.42, 0.365)
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert mock_light.colour_xy == (0.0, 0.0)

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_XY_COLOR: (0.1, 0.1)},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_XY_COLOR] == (0.1, 0.1)
    assert attributes[ATTR_COLOR_MODE] == ColorMode.XY
    assert mock_light.colour_xy == (0.1, 0.1)


async def test_light_control_effect_xy(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test color effect control."""

    mock_light.supports_effects = True
    mock_light.effect = EffectType.NONE
    mock_light.effect_speed = EFFECT_SPEED

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = f"light.{TEST_DEVICE_NAME.lower().replace(' ', '_')}"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.NONE.name
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EFFECT: EffectType.CANDLE.name,
            ATTR_XY_COLOR: (0.3, 0.3),
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.CANDLE.name
    assert attributes[ATTR_XY_COLOR] == (0.3, 0.3)
    assert attributes[ATTR_COLOR_MODE] == ColorMode.XY
    assert mock_light.effect == EffectType.CANDLE
    assert mock_light.effect_speed == EFFECT_SPEED
    assert not mock_light.colour_temp_mode

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_XY_COLOR: (0.5, 0.5),
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.CANDLE.name
    assert attributes[ATTR_XY_COLOR] == (0.5, 0.5)
    assert attributes[ATTR_COLOR_MODE] == ColorMode.XY
    assert mock_light.effect == EffectType.CANDLE
    assert mock_light.effect_speed == EFFECT_SPEED
    assert not mock_light.colour_temp_mode


async def test_light_control_effect_temp(
    hass: HomeAssistant,
    mock_light: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test temperature effect control."""

    mock_light.supports_effects = True
    mock_light.effect = EffectType.NONE
    mock_light.effect_speed = EFFECT_SPEED

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = f"light.{TEST_DEVICE_NAME.lower().replace(' ', '_')}"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.NONE.name
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: EffectType.COSMOS.name},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.COSMOS.name
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert mock_light.effect == EffectType.COSMOS
    assert mock_light.effect_speed == EFFECT_SPEED
    assert mock_light.colour_temp_mode

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_EFFECT: EffectType.CANDLE.name,
            ATTR_XY_COLOR: (0.3, 0.3),
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_EFFECT] == EffectType.CANDLE.name
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 4000
    assert mock_light.effect == EffectType.CANDLE
    assert mock_light.effect_speed == EFFECT_SPEED
    assert mock_light.colour_temp_mode
