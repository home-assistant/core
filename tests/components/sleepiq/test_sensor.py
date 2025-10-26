"""The tests for SleepIQ sensor platform."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BED_NAME,
    BED_NAME_LOWER,
    SLEEPER_L_ID,
    SLEEPER_L_NAME,
    SLEEPER_L_NAME_LOWER,
    SLEEPER_R_ID,
    SLEEPER_R_NAME,
    SLEEPER_R_NAME_LOWER,
    setup_platform,
)


async def test_sleepnumber_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test the SleepIQ sleepnumber for a bed with two sides."""
    entry = await setup_platform(hass, SENSOR_DOMAIN)

    state = hass.states.get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_sleepnumber"
    )
    assert state.state == "40"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_L_NAME} SleepNumber"
    )

    entry = entity_registry.async_get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_sleepnumber"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_L_ID}_sleep_number"

    state = hass.states.get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_sleepnumber"
    )
    assert state.state == "80"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_R_NAME} SleepNumber"
    )

    entry = entity_registry.async_get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_sleepnumber"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_R_ID}_sleep_number"


async def test_pressure_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test the SleepIQ pressure for a bed with two sides."""
    entry = await setup_platform(hass, SENSOR_DOMAIN)

    state = hass.states.get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_pressure"
    )
    assert state.state == "1000"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_L_NAME} Pressure"
    )

    entry = entity_registry.async_get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_pressure"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_L_ID}_pressure"

    state = hass.states.get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_pressure"
    )
    assert state.state == "1400"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"SleepNumber {BED_NAME} {SLEEPER_R_NAME} Pressure"
    )

    entry = entity_registry.async_get(
        f"sensor.sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_pressure"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_R_ID}_pressure"
