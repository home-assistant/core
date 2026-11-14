"""Services for the Total Connect integration."""

from enum import StrEnum

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class TotalConnectService(StrEnum):
    """Store keys for Total Connect services."""

    ARM_AWAY_INSTANT = "arm_away_instant"
    ARM_HOME_INSTANT = "arm_home_instant"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Total Connect integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        TotalConnectService.ARM_AWAY_INSTANT,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema=None,
        func="async_alarm_arm_away_instant",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        TotalConnectService.ARM_HOME_INSTANT,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema=None,
        func="async_alarm_arm_home_instant",
    )
