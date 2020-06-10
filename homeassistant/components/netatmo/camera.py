"""Support for the Netatmo cameras."""
import logging

import pyatmo
import requests
import voluptuous as vol

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SUPPORT_STREAM,
    Camera,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    ATTR_PERSON,
    ATTR_PERSONS,
    ATTR_PSEUDO,
    DATA_HANDLER,
    DATA_PERSONS,
    DOMAIN,
    MANUFACTURER,
    MODELS,
    SERVICE_SETPERSONAWAY,
    SERVICE_SETPERSONSHOME,
)
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

CONF_HOME = "home"
CONF_CAMERAS = "cameras"
CONF_QUALITY = "quality"

DEFAULT_QUALITY = "high"

VALID_QUALITIES = ["high", "medium", "low", "poor"]

SCHEMA_SERVICE_SETLIGHTAUTO = vol.Schema(
    {
        # vol.Optional(ATTR_ENTITY_ID): cv.entity_domain(CAMERA_DOMAIN),
        # vol.Required(ATTR_HOME_NAME): cv.string,
    }
)

SCHEMA_SERVICE_SETPERSONSHOME = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_domain(CAMERA_DOMAIN),
        vol.Required(ATTR_PERSONS): vol.All(cv.ensure_list, [cv.string]),
    }
)

SCHEMA_SERVICE_SETPERSONAWAY = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_domain(CAMERA_DOMAIN),
        vol.Optional(ATTR_PERSON): cv.string,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera platform."""
    if "access_camera" not in entry.data["token"]["scope"]:
        _LOGGER.info(
            "Cameras are currently not supported with this authentication method"
        )
        return

    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    data_class = "CameraData"

    async def get_entities():
        """Retrieve Netatmo entities."""
        await data_handler.register_data_class(data_class)

        entities = []
        try:
            all_cameras = []
            for home in data_handler.data[data_class].cameras.values():
                for camera in home.values():
                    all_cameras.append(camera)

            for camera in all_cameras:
                _LOGGER.debug("Adding camera %s %s", camera["id"], camera["name"])
                entities.append(
                    NetatmoCamera(
                        data_handler,
                        data_class,
                        camera["id"],
                        camera["type"],
                        camera["home_id"],
                        DEFAULT_QUALITY,
                    )
                )

            for person_id, person_data in data_handler.data[data_class].persons.items():
                hass.data[DOMAIN][DATA_PERSONS][person_id] = person_data.get(
                    ATTR_PSEUDO
                )
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")

        await data_handler.unregister_data_class(data_class)
        return entities

    async_add_entities(await get_entities(), True)

    platform = entity_platform.current_platform.get()

    if data_handler.data[data_class] is not None:
        platform.async_register_entity_service(
            SERVICE_SETPERSONSHOME,
            SCHEMA_SERVICE_SETPERSONSHOME,
            "_service_setpersonshome",
        )
        platform.async_register_entity_service(
            SERVICE_SETPERSONAWAY,
            SCHEMA_SERVICE_SETPERSONAWAY,
            "_service_setpersonaway",
        )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo camera platform."""
    return


class NetatmoCamera(Camera, NetatmoBase):
    """Representation of a Netatmo camera."""

    def __init__(
        self, data_handler, data_class, camera_id, camera_type, home_id, quality,
    ):
        """Set up for access to the Netatmo camera images."""
        Camera.__init__(self)
        NetatmoBase.__init__(self, data_handler)

        self._data_classes.append({"name": data_class})

        self._camera_id = camera_id
        self._home_id = home_id
        self._camera_name = self._data.get_camera(camera_id=camera_id).get("name")
        self._name = f"{MANUFACTURER} {self._camera_name}"
        self._camera_type = camera_type
        self._unique_id = f"{self._camera_id}-{self._camera_type}"
        self._quality = quality
        self._vpnurl = None
        self._localurl = None
        self._status = None
        self._sd_status = None
        self._alim_status = None
        self._is_local = None

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await NetatmoBase.async_added_to_hass(self)

        async def handle_event(event):
            """Handle webhook events."""
            data = event.data["data"]

            if not data.get("event_type"):
                return

            if not data.get("camera_id"):
                return

            if (
                data["home_id"] == self._home_id
                and data["camera_id"] == self._camera_id
            ):
                if data["push_type"] in ["NACamera-off", "NACamera-disconnection"]:
                    self.is_streaming = False
                    self._status = "off"
                elif data["push_type"] in ["NACamera-on", "NACamera-connection"]:
                    self.is_streaming = True
                    self._status = "on"

                self.schedule_update_ha_state()
                return

        self.hass.bus.async_listen("netatmo_event", handle_event)

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get(
                    f"{self._localurl}/live/snapshot_720.jpg", timeout=10
                )
            elif self._vpnurl:
                response = requests.get(
                    f"{self._vpnurl}/live/snapshot_720.jpg", timeout=10, verify=True,
                )
            else:
                _LOGGER.error("Welcome/Presence VPN URL is None")
                (self._vpnurl, self._localurl) = self._data.camera_urls(
                    camera_id=self._camera_id
                )
                return None
        except requests.exceptions.RequestException as error:
            _LOGGER.info("Welcome/Presence URL changed: %s", error)
            self._data.update_camera_urls(camera_id=self._camera_id)
            (self._vpnurl, self._localurl) = self._data.camera_urls(
                camera_id=self._camera_id
            )
            return None
        return response.content

    @property
    def name(self):
        """Return the name of this Netatmo camera device."""
        return self._name

    @property
    def device_info(self):
        """Return the device info for the sensor."""
        return {
            "identifiers": {(DOMAIN, self._camera_id)},
            "name": self._camera_name,
            "manufacturer": MANUFACTURER,
            "model": MODELS[self._camera_type],
        }

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""
        return {
            "id": self._camera_id,
            "status": self._status,
            "sd_status": self._sd_status,
            "alim_status": self._alim_status,
            "is_local": self._is_local,
            "vpn_url": self._vpnurl,
            "local_url": self._localurl,
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._alim_status == "on")

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def brand(self):
        """Return the camera brand."""
        return MANUFACTURER

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return bool(self._status == "on")

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    def turn_off(self):
        """Turn off camera."""
        self._data.set_state(
            home_id=self._home_id, camera_id=self._camera_id, monitoring="off"
        )

    def turn_on(self):
        """Turn on camera."""
        self._data.set_state(
            home_id=self._home_id, camera_id=self._camera_id, monitoring="on"
        )

    async def stream_source(self):
        """Return the stream source."""
        url = "{0}/live/files/{1}/index.m3u8"
        if self._localurl:
            return url.format(self._localurl, self._quality)
        return url.format(self._vpnurl, self._quality)

    @property
    def model(self):
        """Return the camera model."""
        return MODELS[self._camera_type]

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        camera = self._data.get_camera(self._camera_id)
        self._vpnurl, self._localurl = self._data.camera_urls(self._camera_id)
        self._status = camera.get("status")
        self._sd_status = camera.get("sd_status")
        self._alim_status = camera.get("alim_status")
        self._is_local = camera.get("is_local")
        self.is_streaming = bool(self._status == "on")

    def _service_setpersonshome(self, **kwargs):
        """Service to change current home schedule."""
        persons = kwargs.get(ATTR_PERSONS)
        person_ids = []
        for person in persons:
            for pid, data in self._data.persons.items():
                if data.get("pseudo") == person:
                    person_ids.append(pid)

        self._data.set_persons_home(person_ids=person_ids, home_id=self._home_id)
        _LOGGER.info("Set %s as at home", persons)

    def _service_setpersonaway(self, **kwargs):
        """Service to mark a person as away or set the home as empty."""
        person = kwargs.get(ATTR_PERSON)
        person_id = None
        if person:
            for pid, data in self._data.persons.items():
                if data.get("pseudo") == person:
                    person_id = pid

        if person_id is not None:
            self._data.set_persons_away(
                person_id=person_id, home_id=self._home_id,
            )
            _LOGGER.info("Set %s as away", person)

        else:
            self._data.set_persons_away(
                person_id=person_id, home_id=self._home_id,
            )
            _LOGGER.info("Set home as empty")
