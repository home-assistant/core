"""Support for the Netatmo camera lights."""
import logging

import pyatmo
import requests

from homeassistant.components.light import Light

from .camera import CameraData
from .const import AUTH, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera light platform."""

    def get_devices():
        """Retrieve Netatmo devices."""
        devices = []
        try:
            camera_data = CameraData(hass, hass.data[DOMAIN][entry.entry_id][AUTH])
            for camera in camera_data.get_all_cameras():
                if camera["type"] == "NOC":
                    _LOGGER.debug("Setting up camera %s", camera["id"])
                    devices.append(NetatmoLight(camera_data, camera["id"]))
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")
        return devices

    async_add_entities(await hass.async_add_executor_job(get_devices), True)


class NetatmoLight(Light):
    """Representation of a Netatmo Presence camera light."""

    def __init__(self, camera_data: CameraData, camera_id: str):
        """Initialize a Netatmo Presence camera light."""
        self._camera_id = camera_id
        self._data = camera_data
        self._camera_type = self._data.camera_data.cameraById(camera_id).get("type")
        self._name = (
            f"{MANUFACTURER} {self._data.camera_data.cameraById(camera_id).get('name')}"
        )
        self._is_on = False
        self._unique_id = f"{self._camera_id}-{self._camera_type}-light"
        self._vpnurl = self._localurl = None
        self._verify_ssl = True

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
            "manufacturer": MANUFACTURER,
            "model": self._camera_type,
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
        _LOGGER.debug("Set the flood light on for the camera '%s'", self._name)
        self._set_light_mode("on")
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        _LOGGER.debug("Set the flood light off for the camera '%s'", self._name)
        self._set_light_mode("off")
        self._is_on = False
        self.schedule_update_ha_state()

    # Netatmo Presence specific camera methods.

    def update(self):
        """Update the camera data."""
        self._data.update()
        (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
            cid=self._camera_id
        )

    def _set_light_mode(self, mode: str):
        """Set light mode ('auto', 'on', 'off')."""
        try:
            config = f'{{"mode":"{mode}"}}'
            if self._localurl:
                requests.get(
                    f"{self._localurl}/command/floodlight_set_config?config="
                    f"{config}",
                    timeout=10,
                )
            elif self._vpnurl:
                requests.get(
                    f"{self._vpnurl}/command/floodlight_set_config?config=" f"{config}",
                    timeout=10,
                    verify=self._verify_ssl,
                )
            else:
                _LOGGER.error("Presence VPN URL is None")
                self._data.update()
                (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                    cid=self._camera_id
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.error("Presence URL changed: %s", error)
            self._data.update()
            (self._vpnurl, self._localurl) = self._data.camera_data.cameraUrls(
                cid=self._camera_id
            )
            return None
        else:
            self.async_schedule_update_ha_state(True)

    # def set_light_auto(self):
    #     """Set flood light in automatic mode."""
    #     _LOGGER.debug(
    #         "Set the flood light in automatic mode for the camera '%s'", self._name
    #     )
    #     self._set_light_mode("auto")
