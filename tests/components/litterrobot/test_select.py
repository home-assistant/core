"""Test the Litter-Robot select entity."""
from unittest.mock import AsyncMock, MagicMock

from pylitterbot import LitterRobot3, LitterRobot4
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

SELECT_ENTITY_ID = "select.test_clean_cycle_wait_time_minutes"
PANEL_BRIGHTNESS_ENTITY_ID = "select.test_panel_brightness"


async def test_wait_time_select(
    hass: HomeAssistant, mock_account, entity_registry: er.EntityRegistry
) -> None:
    """Tests the wait time select entity."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    select = hass.states.get(SELECT_ENTITY_ID)
    assert select

    entity_entry = entity_registry.async_get(SELECT_ENTITY_ID)
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

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )
    assert not mock_account.robots[0].set_wait_time.called


async def test_panel_brightness_select(
    hass: HomeAssistant,
    mock_account_with_litterrobot_4: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests the wait time select entity."""
    await setup_integration(hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN)

    select = hass.states.get(PANEL_BRIGHTNESS_ENTITY_ID)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 3

    entity_entry = entity_registry.async_get(PANEL_BRIGHTNESS_ENTITY_ID)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: PANEL_BRIGHTNESS_ENTITY_ID}

    robot: LitterRobot4 = mock_account_with_litterrobot_4.robots[0]
    robot.set_panel_brightness = AsyncMock(return_value=True)
    count = 0
    for option in select.attributes[ATTR_OPTIONS]:
        count += 1
        data[ATTR_OPTION] = option

        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert robot.set_panel_brightness.call_count == count
