"""Support for FFmpeg."""

from enum import StrEnum

import probatio

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    SIGNAL_FFMPEG_RESTART,
    SIGNAL_FFMPEG_START,
    SIGNAL_FFMPEG_STOP,
)


class FFmpegService(StrEnum):
    """Store keys for FFmpeg services."""

    RESTART = "restart"
    START = "start"
    STOP = "stop"


SERVICE_FFMPEG_SCHEMA = probatio.Schema(
    {probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids}
)


async def _async_service_handle(service: ServiceCall) -> None:
    """Handle service ffmpeg process."""
    entity_ids: list[str] | None = service.data.get(ATTR_ENTITY_ID)

    if service.service == FFmpegService.START:
        async_dispatcher_send(service.hass, SIGNAL_FFMPEG_START, entity_ids)
    elif service.service == FFmpegService.STOP:
        async_dispatcher_send(service.hass, SIGNAL_FFMPEG_STOP, entity_ids)
    else:
        async_dispatcher_send(service.hass, SIGNAL_FFMPEG_RESTART, entity_ids)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register FFmpeg services."""

    hass.services.async_register(
        DOMAIN, FFmpegService.START, _async_service_handle, schema=SERVICE_FFMPEG_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, FFmpegService.STOP, _async_service_handle, schema=SERVICE_FFMPEG_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        FFmpegService.RESTART,
        _async_service_handle,
        schema=SERVICE_FFMPEG_SCHEMA,
    )
