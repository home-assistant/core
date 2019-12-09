"""Support for the Netatmo camera lights."""
import logging

import pyatmo

# import requests

from homeassistant.components.light import Light

# from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    #     async_dispatcher_connect,
)

from .const import AUTH, DOMAIN, MANUFAKTURER
from .camera import CameraData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Netatmo camera platform."""

    def get_devices():
        """Retrieve Netatmo devices."""
        devices = []
        try:
            camera_data = CameraData(hass, hass.data[DOMAIN][AUTH])
            for camera_id in camera_data.get_camera_ids():
                _LOGGER.debug("Setting up camera %s", camera_id)
                camera_type = camera_data.get_camera_type(camera_id=camera_id)
                if camera_type == "NOC":
                    devices.append(NetatmoLight(camera_id))
            camera_data.get_persons()
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")
        return devices

    async_add_entities(await hass.async_add_executor_job(get_devices), True)

    async def async_service_handler(call):
        """Handle service call."""
        _LOGGER.debug(
            "Service handler invoked with service=%s and data=%s",
            call.service,
            call.data,
        )
        service = call.service
        entity_id = call.data["entity_id"][0]
        async_dispatcher_send(hass, f"{service}_{entity_id}")

    # hass.services.async_register(
    #     DOMAIN, "set_light_auto", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )
    # hass.services.async_register(
    #     DOMAIN, "set_light_on", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )
    # hass.services.async_register(
    #     DOMAIN, "set_light_off", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )


class NetatmoLight(Light):
    """Representation of a Netatmo Presence camera light."""

    def __init__(self, camera_id):
        """Initialize a Netatmo Presence camera light."""
        self._camera_id = camera_id
        self._name = f"{MANUFAKTURER} {camera_id}"
        self._is_on = False

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def should_poll(self):
        """Return if we should poll this device."""
        return True

    @property
    def assumed_state(self) -> bool:
        """Return False if unable to access real state of the entity."""
        return False

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        # TODO
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        # TODO
        self._is_on = False
        self.schedule_update_ha_state()
