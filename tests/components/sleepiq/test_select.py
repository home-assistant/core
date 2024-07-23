"""Tests for the SleepIQ select platform."""

from unittest.mock import MagicMock

from asyncsleepiq import FootWarmingTemps

from homeassistant.components.select import DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_OPTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BED_ID,
    BED_NAME,
    BED_NAME_LOWER,
    FOOT_WARM_TIME,
    PRESET_L_STATE,
    PRESET_R_STATE,
    SLEEPER_L_ID,
    SLEEPER_L_NAME,
    SLEEPER_L_NAME_LOWER,
    SLEEPER_R_ID,
    SLEEPER_R_NAME,
    SLEEPER_R_NAME_LOWER,
    setup_platform,
)


async def test_split_foundation_preset(
    hass: HomeAssistant, mock_asyncsleepiq: MagicMock
) -> None:
    """Test the SleepIQ select entity for split foundation presets."""
    entry = await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    state = hass.states.get(
        f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset_right"
    )
    assert state.state == PRESET_R_STATE
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} Foundation Preset Right"
    )

    entry = entity_registry.async_get(
        f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset_right"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_preset_R"

    state = hass.states.get(
        f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset_left"
    )
    assert state.state == PRESET_L_STATE
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} Foundation Preset Left"
    )

    entry = entity_registry.async_get(
        f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset_left"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_preset_L"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset_left",
            ATTR_OPTION: "Zero G",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].foundation.presets[0].set_preset.assert_called_once()
    mock_asyncsleepiq.beds[BED_ID].foundation.presets[0].set_preset.assert_called_with(
        "Zero G"
    )


async def test_single_foundation_preset(
    hass: HomeAssistant, mock_asyncsleepiq_single_foundation: MagicMock
) -> None:
    """Test the SleepIQ select entity for single foundation presets."""
    entry = await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    state = hass.states.get(f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset")
    assert state.state == PRESET_R_STATE
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} Foundation Preset"
    )

    entry = entity_registry.async_get(
        f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_preset"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.sleepnumber_{BED_NAME_LOWER}_foundation_preset",
            ATTR_OPTION: "Zero G",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq_single_foundation.beds[BED_ID].foundation.presets[
        0
    ].set_preset.assert_called_once()
    mock_asyncsleepiq_single_foundation.beds[BED_ID].foundation.presets[
        0
    ].set_preset.assert_called_with("Zero G")


async def test_foot_warmer(hass: HomeAssistant, mock_asyncsleepiq: MagicMock) -> None:
    """Test the SleepIQ select entity for foot warmers."""
    entry = await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    state = hass.states.get(
        f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_foot_warmer"
    )
    assert state.state == FootWarmingTemps.MEDIUM.name.lower()
    assert state.attributes.get(ATTR_ICON) == "mdi:heat-wave"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_L_NAME} Foot Warmer"
    )

    entry = entity_registry.async_get(
        f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_foot_warmer"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_L_ID}_foot_warmer"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_foot_warmer",
            ATTR_OPTION: "off",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].foundation.foot_warmers[
        0
    ].turn_off.assert_called_once()

    state = hass.states.get(
        f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_foot_warmer"
    )
    assert state.state == FootWarmingTemps.OFF.name.lower()
    assert state.attributes.get(ATTR_ICON) == "mdi:heat-wave"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_R_NAME} Foot Warmer"
    )

    entry = entity_registry.async_get(
        f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_foot_warmer"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_R_ID}_foot_warmer"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"select.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_foot_warmer",
            ATTR_OPTION: "high",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].foundation.foot_warmers[
        1
    ].turn_on.assert_called_once()
    mock_asyncsleepiq.beds[BED_ID].foundation.foot_warmers[
        1
    ].turn_on.assert_called_with(FootWarmingTemps.HIGH, FOOT_WARM_TIME)
