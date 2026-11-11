"""Services for Agent DVR."""

from enum import StrEnum

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class AgentDvrService(StrEnum):
    """Store keys for Agent DVR services."""

    START_RECORDING = "start_recording"
    STOP_RECORDING = "stop_recording"
    ENABLE_ALERTS = "enable_alerts"
    DISABLE_ALERTS = "disable_alerts"
    SNAPSHOT = "snapshot"


CAMERA_SERVICES = {
    AgentDvrService.ENABLE_ALERTS: "async_enable_alerts",
    AgentDvrService.DISABLE_ALERTS: "async_disable_alerts",
    AgentDvrService.START_RECORDING: "async_start_recording",
    AgentDvrService.STOP_RECORDING: "async_stop_recording",
    AgentDvrService.SNAPSHOT: "async_snapshot",
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    for service_name, method in CAMERA_SERVICES.items():
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=CAMERA_DOMAIN,
            schema=None,
            func=method,
        )
