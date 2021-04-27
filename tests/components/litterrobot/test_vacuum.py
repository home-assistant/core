"""Test the Litter-Robot vacuum entity."""
from datetime import timedelta

import pytest

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.components.litterrobot.entity import REFRESH_WAIT_TIME_SECONDS
from homeassistant.components.litterrobot.vacuum import (
    SERVICE_RESET_WASTE_DRAWER,
    SERVICE_SET_SLEEP_MODE,
    SERVICE_SET_WAIT_TIME,
)
from homeassistant.components.vacuum import (
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_DOCKED,
    STATE_ERROR,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import VACUUM_ENTITY_ID
from .conftest import setup_integration

from tests.common import async_fire_time_changed

COMPONENT_SERVICE_DOMAIN = {
    SERVICE_RESET_WASTE_DRAWER: DOMAIN,
    SERVICE_SET_SLEEP_MODE: DOMAIN,
    SERVICE_SET_WAIT_TIME: DOMAIN,
}


async def test_vacuum(hass: HomeAssistant, mock_account):
    """Tests the vacuum entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)
    assert hass.services.has_service(DOMAIN, SERVICE_RESET_WASTE_DRAWER)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED
    assert vacuum.attributes["is_sleeping"] is False


async def test_no_robots(hass: HomeAssistant, mock_account_with_no_robots):
    """Tests the vacuum entity was set up."""
    await setup_integration(hass, mock_account_with_no_robots, PLATFORM_DOMAIN)

    assert not hass.services.has_service(DOMAIN, SERVICE_RESET_WASTE_DRAWER)


async def test_vacuum_with_error(hass: HomeAssistant, mock_account_with_error):
    """Tests a vacuum entity with an error."""
    await setup_integration(hass, mock_account_with_error, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_ERROR


@pytest.mark.parametrize(
    "service,command,extra",
    [
        (SERVICE_START, "start_cleaning", None),
        (SERVICE_TURN_OFF, "set_power_status", None),
        (SERVICE_TURN_ON, "set_power_status", None),
        (
            SERVICE_RESET_WASTE_DRAWER,
            "reset_waste_drawer",
            None,
        ),
        (
            SERVICE_SET_SLEEP_MODE,
            "set_sleep_mode",
            {"enabled": True, "start_time": "22:30"},
        ),
        (
            SERVICE_SET_SLEEP_MODE,
            "set_sleep_mode",
            {"enabled": True},
        ),
        (
            SERVICE_SET_SLEEP_MODE,
            "set_sleep_mode",
            {"enabled": False},
        ),
        (
            SERVICE_SET_WAIT_TIME,
            "set_wait_time",
            {"minutes": 3},
        ),
    ],
)
async def test_commands(hass: HomeAssistant, mock_account, service, command, extra):
    """Test sending commands to the vacuum."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    data = {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}
    if extra:
        data.update(extra)

    await hass.services.async_call(
        COMPONENT_SERVICE_DOMAIN.get(service, PLATFORM_DOMAIN),
        service,
        data,
        blocking=True,
    )
    future = utcnow() + timedelta(seconds=REFRESH_WAIT_TIME_SECONDS)
    async_fire_time_changed(hass, future)
    getattr(mock_account.robots[0], command).assert_called_once()


async def test_invalid_commands(
    hass: HomeAssistant, caplog, mock_account_with_side_effects
):
    """Test sending invalid commands to the vacuum."""
    await setup_integration(hass, mock_account_with_side_effects, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WAIT_TIME,
        {ATTR_ENTITY_ID: VACUUM_ENTITY_ID, "minutes": 15},
        blocking=True,
    )
    mock_account_with_side_effects.robots[0].set_wait_time.assert_called_once()
    assert "Invalid command: oops" in caplog.text
