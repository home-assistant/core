"""The tests for SleepIQ binary sensor platform."""

from homeassistant.components.button import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import BED_ID, BED_NAME, BED_NAME_LOWER, setup_platform


async def test_button_calibrate(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test the SleepIQ calibrate button."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    state = hass.states.get(f"button.sleepnumber_{BED_NAME_LOWER}_calibrate")
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == f"SleepNumber {BED_NAME} Calibrate"
    )

    entity = entity_registry.async_get(f"button.sleepnumber_{BED_NAME_LOWER}_calibrate")
    assert entity
    assert entity.unique_id == f"{BED_ID}-calibrate"

    await hass.services.async_call(
        DOMAIN,
        "press",
        {ATTR_ENTITY_ID: f"button.sleepnumber_{BED_NAME_LOWER}_calibrate"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].calibrate.assert_called_once()


async def test_button_stop_pump(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test the SleepIQ stop pump button."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    state = hass.states.get(f"button.sleepnumber_{BED_NAME_LOWER}_stop_pump")
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == f"SleepNumber {BED_NAME} Stop Pump"
    )

    entity = entity_registry.async_get(f"button.sleepnumber_{BED_NAME_LOWER}_stop_pump")
    assert entity
    assert entity.unique_id == f"{BED_ID}-stop-pump"

    await hass.services.async_call(
        DOMAIN,
        "press",
        {ATTR_ENTITY_ID: f"button.sleepnumber_{BED_NAME_LOWER}_stop_pump"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].stop_pump.assert_called_once()
