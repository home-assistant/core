"""The tests for SleepIQ switch platform."""

from homeassistant.components.sleepiq.coordinator import LONGER_UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import BED_ID, BED_NAME, BED_NAME_LOWER, setup_platform

from tests.common import async_fire_time_changed


async def test_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test for successfully setting up the SleepIQ platform."""
    entry = await setup_platform(hass, SWITCH_DOMAIN)

    assert len(entity_registry.entities) == 1

    entry = entity_registry.async_get(f"switch.sleepnumber_{BED_NAME_LOWER}_pause_mode")
    assert entry
    assert entry.original_name == f"SleepNumber {BED_NAME} Pause Mode"
    assert entry.unique_id == f"{BED_ID}-pause-mode"


async def test_switch_set_states(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test button press."""
    await setup_platform(hass, SWITCH_DOMAIN)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: f"switch.sleepnumber_{BED_NAME_LOWER}_pause_mode"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].set_pause_mode.assert_called_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: f"switch.sleepnumber_{BED_NAME_LOWER}_pause_mode"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].set_pause_mode.assert_called_with(True)


async def test_switch_get_states(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test button press."""
    await setup_platform(hass, SWITCH_DOMAIN)

    assert (
        hass.states.get(f"switch.sleepnumber_{BED_NAME_LOWER}_pause_mode").state
        == STATE_OFF
    )
    mock_asyncsleepiq.beds[BED_ID].paused = True

    async_fire_time_changed(hass, utcnow() + LONGER_UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get(f"switch.sleepnumber_{BED_NAME_LOWER}_pause_mode").state
        == STATE_ON
    )
