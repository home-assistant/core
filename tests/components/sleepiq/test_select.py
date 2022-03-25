"""Tests for the SleepIQ select platform."""
from unittest.mock import MagicMock

from homeassistant.components.select import DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_OPTION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.sleepiq.conftest import (
    BED_ID,
    BED_NAME,
    BED_NAME_LOWER,
    PRESET_L_STATE,
    PRESET_R_STATE,
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
