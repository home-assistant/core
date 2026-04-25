"""Services for Agent DVR."""

from __future__ import annotations

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

CAMERA_SERVICES = {
    "enable_alerts": "async_enable_alerts",
    "disable_alerts": "async_disable_alerts",
    "start_recording": "async_start_recording",
    "stop_recording": "async_stop_recording",
    "snapshot": "async_snapshot",
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
