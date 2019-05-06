"""
Support for ONVIF Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.onvif/
"""
import asyncio
import logging
import os

from . import ONVIFHassCamera, SERVICE_PTZ, SERVICE_PTZ_SCHEMA
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA, SUPPORT_STREAM)
from homeassistant.components.camera.const import DOMAIN
from homeassistant.helpers.service import extract_entity_ids

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a ONVIF camera."""
    _LOGGER.debug("Setting up the ONVIF camera platform")

    async def async_handle_ptz(service):
        """Handle PTZ service call."""
        pan = service.data.get(ATTR_PAN, None)
        tilt = service.data.get(ATTR_TILT, None)
        zoom = service.data.get(ATTR_ZOOM, None)
        all_cameras = hass.data[ONVIF_DATA][ENTITIES]
        entity_ids = extract_entity_ids(hass, service)
        target_cameras = []
        if not entity_ids:
            target_cameras = all_cameras
        else:
            target_cameras = [camera for camera in all_cameras
                              if camera.entity_id in entity_ids]
        for camera in target_cameras:
            await camera.async_perform_ptz(pan, tilt, zoom)

    hass.services.async_register(DOMAIN, SERVICE_PTZ, async_handle_ptz,
                                 schema=SERVICE_PTZ_SCHEMA)

    _LOGGER.debug("Constructing the ONVIFHassCamera")

    hass_camera = ONVIFHassCamera(hass, config)

    await hass_camera.async_initialize()

    async_add_entities([hass_camera])
    return