"""Support for the Netatmo camera lights."""
import logging

import pyatmo

# import requests

from homeassistant.components.light import Light

# from homeassistant.const import STATE_ON, STATE_OFF

# from homeassistant.helpers.dispatcher import (
#     async_dispatcher_send,
#         async_dispatcher_connect,
# )

from .const import AUTH, DOMAIN, MANUFAKTURER
from .camera import CameraData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Netatmo camera light platform."""

    def get_devices():
        """Retrieve Netatmo devices."""
        devices = []
        try:
            camera_data = CameraData(hass, hass.data[DOMAIN][AUTH])
            for camera_id in camera_data.get_camera_ids():
                camera_type = camera_data.get_camera_type(camera_id=camera_id)
                if camera_type == "NOC":
                    _LOGGER.debug("Setting up camera %s", camera_id)
                    devices.append(NetatmoLight(camera_id, camera_data))
            camera_data.get_persons()
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")
        return devices

    async_add_entities(await hass.async_add_executor_job(get_devices), True)


class NetatmoLight(Light):
    """Representation of a Netatmo Presence camera light."""

    def __init__(self, camera_id: str, camera_data: CameraData):
        """Initialize a Netatmo Presence camera light."""
        self._camera_id = camera_id
        self._camera_data = camera_data
        self._module_type = camera_data.camera_data[camera_id].get("type")
        self._name = f"{MANUFAKTURER} {camera_data.camera_data[camera_id].get('name')}"
        self._is_on = False
        self._unique_id = f"{self._camera_id}-{self._name}-light"

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._name,
            "manufacturer": MANUFAKTURER,
            "model": self._module_type,
        }

    @property
    def unique_id(self):
        """Return the unique ID for this light."""
        return self._unique_id

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

    # async def async_service_handler(call):
    #     """Handle service call."""
    #     _LOGGER.debug(
    #         "Service handler invoked with service=%s and data=%s",
    #         call.service,
    #         call.data,
    #     )
    #     service = call.service
    #     entity_id = call.data["entity_id"][0]
    #     async_dispatcher_send(hass, f"{service}_{entity_id}")

    # hass.services.async_register(
    #     DOMAIN, "set_light_auto", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )
    # hass.services.async_register(
    #     DOMAIN, "set_light_on", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )
    # hass.services.async_register(
    #     DOMAIN, "set_light_off", async_service_handler, CAMERA_SERVICE_SCHEMA
    # )

    # async def async_added_to_hass(self):
    #     """Subscribe to signals and add camera to list."""
    #     _LOGGER.debug("Registering services for entity_id=%s", self.entity_id)
    #     async_dispatcher_connect(
    #         self.hass, f"set_light_auto_{self.entity_id}", self.set_light_auto
    #     )
    #     async_dispatcher_connect(
    #         self.hass, f"set_light_on_{self.entity_id}", self.set_light_on
    #     )
    #     async_dispatcher_connect(
    #         self.hass, f"set_light_off_{self.entity_id}", self.set_light_off
    #     )

    # # Netatmo Presence specific camera method.

    # def set_light_auto(self):
    #     """Set flood light in automatic mode."""
    #     _LOGGER.debug(
    #         "Set the flood light in automatic mode for the camera '%s'", self._name
    #     )
    #     self._set_light_mode("auto")

    # def set_light_on(self):
    #     """Set flood light on."""
    #     _LOGGER.debug("Set the flood light on for the camera '%s'", self._name)
    #     self._set_light_mode("on")

    # def set_light_off(self):
    #     """Set flood light off."""
    #     _LOGGER.debug("Set the flood light off for the camera '%s'", self._name)
    #     self._set_light_mode("off")

    # def _set_light_mode(self, mode):
    #     """Set light mode ('auto', 'on', 'off')."""
    #     if self.model == "Presence":
    #         try:
    #             config = '{"mode":"' + mode + '"}'
    #             if self._localurl:
    #                 requests.get(
    #                     f"{self._localurl}/command/floodlight_set_config?config="
    #                     f"{config}",
    #                     timeout=10,
    #                 )
    #             elif self._vpnurl:
    #                 requests.get(
    #                     f"{self._vpnurl}/command/floodlight_set_config?config="
    #                     f"{config}",
    #                     timeout=10,
    #                     verify=self._verify_ssl,
    #                 )
    #             else:
    #                 _LOGGER.error("Presence VPN URL is None")
    #                 self._data.update()
    #                 (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
    #                     cid=self._camera_id
    #                 )
    #                 return None
    #         except requests.exceptions.RequestException as error:
    #             _LOGGER.error("Presence URL changed: %s", error)
    #             self._data.update()
    #             (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
    #                 cid=self._camera_id
    #             )
    #             return None
    #         else:
    #             self.async_schedule_update_ha_state(True)
    #     else:
    #         _LOGGER.error("Unsupported camera model for light mode")
