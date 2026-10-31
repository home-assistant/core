"""The tests for SleepIQ number platform."""

from http import HTTPStatus
from unittest.mock import MagicMock

from asyncsleepiq import SleepIQAPIException, SleepIQTimeoutException
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.sleepiq.coordinator import LONGER_UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BED_ID,
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

FAVORITE_L_ENTITY_ID = (
    f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}"
    f"_{SLEEPER_L_NAME_LOWER}_favorite_firmness"
)


async def test_firmness(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test the SleepIQ firmness number values for a bed with two sides."""
    entry = await setup_platform(hass, NUMBER_DOMAIN)

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_firmness"
    )
    assert state.state == "40.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_MIN) == 5
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 5
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} {SLEEPER_L_NAME} Firmness"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_firmness"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_L_ID}_firmness"

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_firmness"
    )
    assert state.state == "80.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_MIN) == 5
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 5
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} {SLEEPER_R_NAME} Firmness"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_R_NAME_LOWER}_firmness"
    )
    assert entry
    assert entry.unique_id == f"{SLEEPER_R_ID}_firmness"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: (
                f"number.{BED_NAME_LOWER}_sleepnumber"
                f"_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_firmness"
            ),
            ATTR_VALUE: 42,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].sleepers[0].set_sleepnumber.assert_called_once()
    mock_asyncsleepiq.beds[BED_ID].sleepers[0].set_sleepnumber.assert_called_with(42)


async def test_favorite_firmness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
) -> None:
    """Test the SleepIQ favorite firmness number for each side."""
    await setup_platform(hass, NUMBER_DOMAIN)

    state = hass.states.get(FAVORITE_L_ENTITY_ID)
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed-outline"
    assert state.attributes.get(ATTR_MIN) == 5
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 5
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} {SLEEPER_L_NAME} Favorite Firmness"
    )
    entry = entity_registry.async_get(FAVORITE_L_ENTITY_ID)
    assert entry
    assert entry.unique_id == f"{SLEEPER_L_ID}_favorite_firmness"

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}"
        f"_{SLEEPER_R_NAME_LOWER}_favorite_firmness"
    )
    assert state.state == "65.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: FAVORITE_L_ENTITY_ID, ATTR_VALUE: 45},
        blocking=True,
    )

    sleeper = mock_asyncsleepiq.beds[BED_ID].sleepers[0]
    sleeper.set_favsleepnumber.assert_called_once_with(45)
    sleeper.set_sleepnumber.assert_not_called()
    assert hass.states.get(FAVORITE_L_ENTITY_ID).state == "45.0"

    # A favorite changed in the Sleep Number app arrives on the next poll.
    sleeper.fav_sleep_number = 60
    freezer.tick(LONGER_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(FAVORITE_L_ENTITY_ID).state == "60.0"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(SleepIQTimeoutException("timed out"), id="timeout"),
        pytest.param(
            SleepIQAPIException(HTTPStatus.INTERNAL_SERVER_ERROR, "server error"),
            id="api_error",
        ),
    ],
)
async def test_favorite_firmness_unavailable_when_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_asyncsleepiq: MagicMock,
    error: Exception,
) -> None:
    """Test favorite firmness is unavailable while the pause coordinator fails."""
    await setup_platform(hass, NUMBER_DOMAIN)
    assert hass.states.get(FAVORITE_L_ENTITY_ID).state == "50.0"

    mock_asyncsleepiq.beds[BED_ID].sleepers[0].fetch_favsleepnumber.side_effect = error
    freezer.tick(LONGER_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(FAVORITE_L_ENTITY_ID).state == STATE_UNAVAILABLE
    assert not hass.config_entries.flow.async_progress()


async def test_actuators(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test SleepIQ actuator position values for adjustable bed."""
    entry = await setup_platform(hass, NUMBER_DOMAIN)

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_right_head_position"
    )
    assert state.state == "60.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 1
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} Right Head Position"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_right_head_position"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_R_H"

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_left_head_position"
    )
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 1
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} Left Head Position"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_left_head_position"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_L_H"

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_foot_position"
    )
    assert state.state == "10.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 100
    assert state.attributes.get(ATTR_STEP) == 1
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} Foot Position"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_foot_position"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_F"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: (
                f"number.{BED_NAME_LOWER}_sleepnumber"
                f"_{BED_NAME_LOWER}_right_head_position"
            ),
            ATTR_VALUE: 42,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_asyncsleepiq.beds[BED_ID].foundation.actuators[
        0
    ].set_position.assert_called_once()
    mock_asyncsleepiq.beds[BED_ID].foundation.actuators[
        0
    ].set_position.assert_called_with(42)


async def test_foot_warmer_timer(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test the SleepIQ foot warmer number values for a bed with two sides."""
    entry = await setup_platform(hass, NUMBER_DOMAIN)

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_foot_warming_timer"
    )
    assert state.state == "120.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:timer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.MINUTES
    assert state.attributes.get(ATTR_MIN) == 30
    assert state.attributes.get(ATTR_MAX) == 360
    assert state.attributes.get(ATTR_STEP) == 30
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} {SLEEPER_L_NAME} Foot Warming Timer"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_foot_warming_timer"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_L_foot_warming_timer"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: (
                f"number.{BED_NAME_LOWER}_sleepnumber"
                f"_{BED_NAME_LOWER}"
                f"_{SLEEPER_L_NAME_LOWER}_foot_warming_timer"
            ),
            ATTR_VALUE: 300,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.beds[BED_ID].foundation.foot_warmers[0].timer == 300


async def test_core_climate_timer(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_asyncsleepiq
) -> None:
    """Test the SleepIQ core climate number values for a bed with two sides."""
    entry = await setup_platform(hass, NUMBER_DOMAIN)

    state = hass.states.get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_core_climate_timer"
    )
    assert state.state == "240.0"
    assert state.attributes.get(ATTR_ICON) == "mdi:timer"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.MINUTES
    assert state.attributes.get(ATTR_MIN) == 0
    assert state.attributes.get(ATTR_MAX) == 600
    assert state.attributes.get(ATTR_STEP) == 30
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{BED_NAME} SleepNumber {BED_NAME} {SLEEPER_L_NAME} Core Climate Timer"
    )

    entry = entity_registry.async_get(
        f"number.{BED_NAME_LOWER}_sleepnumber_{BED_NAME_LOWER}_{SLEEPER_L_NAME_LOWER}_core_climate_timer"
    )
    assert entry
    assert entry.unique_id == f"{BED_ID}_L_core_climate_timer"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: (
                f"number.{BED_NAME_LOWER}_sleepnumber"
                f"_{BED_NAME_LOWER}"
                f"_{SLEEPER_L_NAME_LOWER}_core_climate_timer"
            ),
            ATTR_VALUE: 420,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_asyncsleepiq.beds[BED_ID].foundation.core_climates[0].timer == 420
