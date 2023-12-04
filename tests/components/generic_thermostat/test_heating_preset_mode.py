"""Test the Generic Thermostat preset mode functionality for heating."""
import pytest

from homeassistant.components.climate import (
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
)
from homeassistant.core import HomeAssistant

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENTITY


@pytest.mark.parametrize(
    ("preset", "temp"),
    [
        (PRESET_NONE, 23),
        (PRESET_AWAY, 16),
        (PRESET_COMFORT, 20),
        (PRESET_HOME, 19),
        (PRESET_SLEEP, 17),
        (PRESET_ACTIVITY, 21),
    ],
)
async def test_set_away_mode(hass: HomeAssistant, setup_comp_2, preset, temp) -> None:
    """Test the setting away mode."""
    await common.async_set_temperature(hass, 23)
    await common.async_set_preset_mode(hass, preset)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == temp


@pytest.mark.parametrize(
    ("preset", "temp"),
    [
        (PRESET_NONE, 23),
        (PRESET_AWAY, 16),
        (PRESET_COMFORT, 20),
        (PRESET_HOME, 19),
        (PRESET_SLEEP, 17),
        (PRESET_ACTIVITY, 21),
    ],
)
async def test_set_away_mode_and_restore_prev_temp(
    hass: HomeAssistant, setup_comp_2, preset, temp
) -> None:
    """Test the setting and removing away mode.

    Verify original temperature is restored.
    """
    await common.async_set_temperature(hass, 23)
    await common.async_set_preset_mode(hass, preset)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == temp
    await common.async_set_preset_mode(hass, PRESET_NONE)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 23


@pytest.mark.parametrize(
    ("preset", "temp"),
    [
        (PRESET_NONE, 23),
        (PRESET_AWAY, 16),
        (PRESET_COMFORT, 20),
        (PRESET_HOME, 19),
        (PRESET_SLEEP, 17),
        (PRESET_ACTIVITY, 21),
    ],
)
async def test_set_away_mode_twice_and_restore_prev_temp(
    hass: HomeAssistant, setup_comp_2, preset, temp
) -> None:
    """Test the setting away mode twice in a row.

    Verify original temperature is restored.
    """
    await common.async_set_temperature(hass, 23)
    await common.async_set_preset_mode(hass, preset)
    await common.async_set_preset_mode(hass, preset)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == temp
    await common.async_set_preset_mode(hass, PRESET_NONE)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 23


async def test_set_preset_mode_invalid(hass: HomeAssistant, setup_comp_2) -> None:
    """Test an invalid mode raises an error and ignore case when checking modes."""
    await common.async_set_temperature(hass, 23)
    await common.async_set_preset_mode(hass, "away")
    state = hass.states.get(ENTITY)
    assert state.attributes.get("preset_mode") == "away"
    await common.async_set_preset_mode(hass, "none")
    state = hass.states.get(ENTITY)
    assert state.attributes.get("preset_mode") == "none"
    with pytest.raises(ValueError):
        await common.async_set_preset_mode(hass, "Sleep")
    state = hass.states.get(ENTITY)
    assert state.attributes.get("preset_mode") == "none"
