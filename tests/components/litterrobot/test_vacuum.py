"""Test the Litter-Robot vacuum entity."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components.litterrobot import DOMAIN
from homeassistant.components.litterrobot.entity import REFRESH_WAIT_TIME_SECONDS
from homeassistant.components.litterrobot.vacuum import (
    SERVICE_RESET_WASTE_DRAWER,
    SERVICE_SET_SLEEP_MODE,
    SERVICE_SET_WAIT_TIME,
)
from homeassistant.components.vacuum import (
    ATTR_STATUS,
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


async def test_vacuum(hass: HomeAssistant, mock_account: MagicMock) -> None:
    """Tests the vacuum entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)
    assert hass.services.has_service(DOMAIN, SERVICE_RESET_WASTE_DRAWER)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED
    assert vacuum.attributes["is_sleeping"] is False


async def test_vacuum_status_when_sleeping(
    hass: HomeAssistant, mock_account_with_sleeping_robot: MagicMock
) -> None:
    """Tests the vacuum status when sleeping."""
    await setup_integration(hass, mock_account_with_sleeping_robot, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.attributes.get(ATTR_STATUS) == "Ready (Sleeping)"


async def test_no_robots(
    hass: HomeAssistant, mock_account_with_no_robots: MagicMock
) -> None:
    """Tests the vacuum entity was set up."""
    await setup_integration(hass, mock_account_with_no_robots, PLATFORM_DOMAIN)

    assert not hass.services.has_service(DOMAIN, SERVICE_RESET_WASTE_DRAWER)


async def test_vacuum_with_error(
    hass: HomeAssistant, mock_account_with_error: MagicMock
) -> None:
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
        (SERVICE_RESET_WASTE_DRAWER, "reset_waste_drawer", {"deprecated": True}),
        (
            SERVICE_SET_SLEEP_MODE,
            "set_sleep_mode",
            {"data": {"enabled": True, "start_time": "22:30"}},
        ),
        (SERVICE_SET_SLEEP_MODE, "set_sleep_mode", {"data": {"enabled": True}}),
        (SERVICE_SET_SLEEP_MODE, "set_sleep_mode", {"data": {"enabled": False}}),
        (
            SERVICE_SET_WAIT_TIME,
            "set_wait_time",
            {"data": {"minutes": 3}, "deprecated": True},
        ),
        (
            SERVICE_SET_WAIT_TIME,
            "set_wait_time",
            {"data": {"minutes": "15"}, "deprecated": True},
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_account: MagicMock,
    caplog: pytest.LogCaptureFixture,
    service: str,
    command: str,
    extra: dict[str, Any],
) -> None:
    """Test sending commands to the vacuum."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    extra = extra or {}
    data = {ATTR_ENTITY_ID: VACUUM_ENTITY_ID, **extra.get("data", {})}
    deprecated = extra.get("deprecated", False)

    await hass.services.async_call(
        COMPONENT_SERVICE_DOMAIN.get(service, PLATFORM_DOMAIN),
        service,
        data,
        blocking=True,
    )
    future = utcnow() + timedelta(seconds=REFRESH_WAIT_TIME_SECONDS)
    async_fire_time_changed(hass, future)
    getattr(mock_account.robots[0], command).assert_called_once()
    assert (f"'{DOMAIN}.{service}' service is deprecated" in caplog.text) is deprecated


async def test_invalid_wait_time(hass: HomeAssistant, mock_account: MagicMock) -> None:
    """Test an attempt to send an invalid wait time to the vacuum."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    vacuum = hass.states.get(VACUUM_ENTITY_ID)
    assert vacuum
    assert vacuum.state == STATE_DOCKED

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WAIT_TIME,
            {ATTR_ENTITY_ID: VACUUM_ENTITY_ID, "minutes": 10},
            blocking=True,
        )
    assert not mock_account.robots[0].set_wait_time.called
