"""The tests for SleepIQ switch platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.sleepiq.coordinator import LONGER_UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    BED_ID,
    BED_NAME,
    BED_NAME_LOWER,
    SLEEPER_L_ID,
    SLEEPER_L_NAME,
    SLEEPER_L_NAME_LOWER,
    SLEEPER_R_NAME_LOWER,
    setup_platform,
)

RESPONSIVE_AIR_L = (
    f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}"
    f"_{SLEEPER_L_NAME_LOWER}_responsive_air"
)
RESPONSIVE_AIR_R = (
    f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}"
    f"_{SLEEPER_R_NAME_LOWER}_responsive_air"
)


async def test_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test for successfully setting up the SleepIQ platform."""
    entry = await setup_platform(hass, SWITCH_DOMAIN)

    assert len(entity_registry.entities) == 3

    entry = entity_registry.async_get(
        f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_pause_mode"
    )
    assert entry
    assert entry.original_name == f"SleepNumber {BED_NAME} Pause Mode"
    assert entry.unique_id == f"{BED_ID}-pause-mode"


async def test_switch_set_states(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test button press."""
    await setup_platform(hass, SWITCH_DOMAIN)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {
            ATTR_ENTITY_ID: (
                f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_pause_mode"
            )
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].set_pause_mode.assert_called_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: (
                f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_pause_mode"
            )
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].set_pause_mode.assert_called_with(True)


async def test_switch_get_states(hass: HomeAssistant, mock_asyncsleepiq) -> None:
    """Test button press."""
    await setup_platform(hass, SWITCH_DOMAIN)

    assert (
        hass.states.get(
            f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_pause_mode"
        ).state
        == STATE_OFF
    )
    mock_asyncsleepiq.beds[BED_ID].paused = True

    async_fire_time_changed(hass, utcnow() + LONGER_UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get(
            f"switch.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_pause_mode"
        ).state
        == STATE_ON
    )


async def test_responsive_air(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test the per-side Responsive Air switches."""
    await setup_platform(hass, SWITCH_DOMAIN)

    entry = entity_registry.async_get(RESPONSIVE_AIR_L)
    assert entry
    assert entry.original_name == (
        f"SleepNumber {BED_NAME} {SLEEPER_L_NAME} Responsive Air"
    )
    assert entry.unique_id == f"{SLEEPER_L_ID}_responsive_air"
    assert hass.states.get(RESPONSIVE_AIR_L).state == STATE_ON
    assert hass.states.get(RESPONSIVE_AIR_R).state == STATE_OFF

    sleeper = mock_asyncsleepiq.beds[BED_ID].sleepers[0]
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: RESPONSIVE_AIR_L}, blocking=True
    )
    sleeper.set_responsive_air.assert_called_with(False)
    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: RESPONSIVE_AIR_L}, blocking=True
    )
    sleeper.set_responsive_air.assert_called_with(True)

    # A change made in the Sleep Number app arrives on the next poll.
    sleeper.responsive_air = False
    freezer.tick(LONGER_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(RESPONSIVE_AIR_L).state == STATE_OFF


async def test_responsive_air_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test beds without Responsive Air get no switch and are never polled for it."""
    sleepers = mock_asyncsleepiq.beds[BED_ID].sleepers
    for sleeper in sleepers:
        sleeper.has_responsive_air.return_value = False

    await setup_platform(hass, SWITCH_DOMAIN)
    freezer.tick(LONGER_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(RESPONSIVE_AIR_L) is None
    assert entity_registry.async_get(RESPONSIVE_AIR_R) is None
    for sleeper in sleepers:
        sleeper.fetch_responsive_air.assert_not_called()
