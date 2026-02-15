"""Services for Agent DVR."""

from __future__ import annotations

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN

_DEV_EN_ALT = "enable_alerts"
_DEV_DS_ALT = "disable_alerts"
_DEV_EN_REC = "start_recording"
_DEV_DS_REC = "stop_recording"
_DEV_SNAP = "snapshot"

CAMERA_SERVICES = {
    _DEV_EN_ALT: "async_enable_alerts",
    _DEV_DS_ALT: "async_disable_alerts",
    _DEV_EN_REC: "async_start_recording",
    _DEV_DS_REC: "async_stop_recording",
    _DEV_SNAP: "async_snapshot",
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
