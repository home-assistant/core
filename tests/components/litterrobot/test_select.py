"""Test the Litter-Robot select entity."""
from pylitterbot import LitterRobot3
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .conftest import setup_integration

SELECT_ENTITY_ID = "select.test_clean_cycle_wait_time_minutes"


async def test_wait_time_select(hass: HomeAssistant, mock_account) -> None:
    """Tests the wait time select entity."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    select = hass.states.get(SELECT_ENTITY_ID)
    assert select

    ent_reg = entity_registry.async_get(hass)
    entity_entry = ent_reg.async_get(SELECT_ENTITY_ID)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: SELECT_ENTITY_ID}

    count = 0
    for wait_time in LitterRobot3.VALID_WAIT_TIMES:
        count += 1
        data[ATTR_OPTION] = wait_time

        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert mock_account.robots[0].set_wait_time.call_count == count


async def test_invalid_wait_time_select(hass: HomeAssistant, mock_account) -> None:
    """Tests the wait time select entity with invalid value."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    select = hass.states.get(SELECT_ENTITY_ID)
    assert select

    data = {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "10"}

    with pytest.raises(ValueError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )
    assert not mock_account.robots[0].set_wait_time.called
