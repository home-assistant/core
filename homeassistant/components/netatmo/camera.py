"""Support for the Netatmo cameras."""
import logging

import pyatmo
import requests
import voluptuous as vol

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_CAMERA_LIGHT_MODE,
    ATTR_PERSON,
    ATTR_PERSONS,
    ATTR_PSEUDO,
    CAMERA_LIGHT_MODES,
    DATA_CAMERAS,
    DATA_EVENTS,
    DATA_HANDLER,
    DATA_PERSONS,
    DOMAIN,
    EVENT_TYPE_OFF,
    EVENT_TYPE_ON,
    MANUFACTURER,
    MODELS,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
    SIGNAL_NAME,
)
from .data_handler import CAMERA_DATA_CLASS_NAME
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

DEFAULT_QUALITY = "high"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera platform."""
    if "access_camera" not in entry.data["token"]["scope"]:
        _LOGGER.info(
            "Cameras are currently not supported with this authentication method"
        )
        return

    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    async def get_entities():
        """Retrieve Netatmo entities."""
        await data_handler.register_data_class(
            CAMERA_DATA_CLASS_NAME, CAMERA_DATA_CLASS_NAME, None
        )

        data = data_handler.data

        if not data.get(CAMERA_DATA_CLASS_NAME):
            return []

        data_class = data_handler.data[CAMERA_DATA_CLASS_NAME]

        entities = []
        try:
            all_cameras = []
            for home in data_class.cameras.values():
                for camera in home.values():
                    all_cameras.append(camera)

            for camera in all_cameras:
                _LOGGER.debug("Adding camera %s %s", camera["id"], camera["name"])
                entities.append(
                    NetatmoCamera(
                        data_handler,
                        camera["id"],
                        camera["type"],
                        camera["home_id"],
                        DEFAULT_QUALITY,
                    )
                )

            for person_id, person_data in data_handler.data[
                CAMERA_DATA_CLASS_NAME
            ].persons.items():
                hass.data[DOMAIN][DATA_PERSONS][person_id] = person_data.get(
                    ATTR_PSEUDO
                )
        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")

        return entities

    async_add_entities(await get_entities(), True)

    platform = entity_platform.current_platform.get()

    if data_handler.data[CAMERA_DATA_CLASS_NAME] is not None:
        platform.async_register_entity_service(
            SERVICE_SET_PERSONS_HOME,
            {vol.Required(ATTR_PERSONS): vol.All(cv.ensure_list, [cv.string])},
            "_service_set_persons_home",
        )
        platform.async_register_entity_service(
            SERVICE_SET_PERSON_AWAY,
            {vol.Optional(ATTR_PERSON): cv.string},
            "_service_set_person_away",
        )
        platform.async_register_entity_service(
            SERVICE_SET_CAMERA_LIGHT,
            {vol.Required(ATTR_CAMERA_LIGHT_MODE): vol.In(CAMERA_LIGHT_MODES)},
            "_service_set_camera_light",
        )


class NetatmoCamera(NetatmoBase, Camera):
    """Representation of a Netatmo camera."""

    def __init__(
        self,
        data_handler,
        camera_id,
        camera_type,
        home_id,
        quality,
    ):
        """Set up for access to the Netatmo camera images."""
        Camera.__init__(self)
        super().__init__(data_handler)

        self._data_classes.append(
            {"name": CAMERA_DATA_CLASS_NAME, SIGNAL_NAME: CAMERA_DATA_CLASS_NAME}
        )

        self._id = camera_id
        self._home_id = home_id
        self._device_name = self._data.get_camera(camera_id=camera_id).get("name")
        self._name = f"{MANUFACTURER} {self._device_name}"
        self._model = camera_type
        self._unique_id = f"{self._id}-{self._model}"
        self._quality = quality
        self._vpnurl = None
        self._localurl = None
        self._status = None
        self._sd_status = None
        self._alim_status = None
        self._is_local = None

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        for event_type in (EVENT_TYPE_OFF, EVENT_TYPE_ON):
            self._listeners.append(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )

        self.hass.data[DOMAIN][DATA_CAMERAS][self._id] = self._device_name

    @callback
    def handle_event(self, event):
        """Handle webhook events."""
        data = event["data"]

        if not data.get("camera_id"):
            return

        if data["home_id"] == self._home_id and data["camera_id"] == self._id:
            if data["push_type"] in ["NACamera-off", "NACamera-disconnection"]:
                self.is_streaming = False
                self._status = "off"
            elif data["push_type"] in ["NACamera-on", "NACamera-connection"]:
                self.is_streaming = True
                self._status = "on"

            self.async_write_ha_state()
            return

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            if self._localurl:
                response = requests.get(
                    f"{self._localurl}/live/snapshot_720.jpg", timeout=10
                )
            elif self._vpnurl:
                response = requests.get(
                    f"{self._vpnurl}/live/snapshot_720.jpg",
                    timeout=10,
                    verify=True,
                )
            else:
                _LOGGER.error("Welcome/Presence VPN URL is None")
                (self._vpnurl, self._localurl) = self._data.camera_urls(
                    camera_id=self._id
                )
                return None

        except requests.exceptions.RequestException as error:
            _LOGGER.info("Welcome/Presence URL changed: %s", error)
            self._data.update_camera_urls(camera_id=self._id)
            (self._vpnurl, self._localurl) = self._data.camera_urls(camera_id=self._id)
            return None

        return response.content

    @property
    def device_state_attributes(self):
        """Return the Netatmo-specific camera state attributes."""
        return {
            "id": self._id,
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
        return bool(self._alim_status == "on" or self._status == "disconnected")

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
            home_id=self._home_id, camera_id=self._id, monitoring="off"
        )

    def turn_on(self):
        """Turn on camera."""
        self._data.set_state(home_id=self._home_id, camera_id=self._id, monitoring="on")

    async def stream_source(self):
        """Return the stream source."""
        url = "{0}/live/files/{1}/index.m3u8"
        if self._localurl:
            return url.format(self._localurl, self._quality)
        return url.format(self._vpnurl, self._quality)

    @property
    def model(self):
        """Return the camera model."""
        return MODELS[self._model]

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        camera = self._data.get_camera(self._id)
        self._vpnurl, self._localurl = self._data.camera_urls(self._id)
        self._status = camera.get("status")
        self._sd_status = camera.get("sd_status")
        self._alim_status = camera.get("alim_status")
        self._is_local = camera.get("is_local")
        self.is_streaming = bool(self._status == "on")

        if self._model == "NACamera":  # Smart Indoor Camera
            self.hass.data[DOMAIN][DATA_EVENTS][self._id] = self.process_events(
                self._data.events.get(self._id, {})
            )
        elif self._model == "NOC":  # Smart Outdoor Camera
            self.hass.data[DOMAIN][DATA_EVENTS][self._id] = self.process_events(
                self._data.outdoor_events.get(self._id, {})
            )

    def process_events(self, events):
        """Add meta data to events."""
        for event in events.values():
            if "video_id" not in event:
                continue
            if self._is_local:
                event[
                    "media_url"
                ] = f"{self._localurl}/vod/{event['video_id']}/files/{self._quality}/index.m3u8"
            else:
                event[
                    "media_url"
                ] = f"{self._vpnurl}/vod/{event['video_id']}/files/{self._quality}/index.m3u8"
        return events

    def _service_set_persons_home(self, **kwargs):
        """Service to change current home schedule."""
        persons = kwargs.get(ATTR_PERSONS)
        person_ids = []
        for person in persons:
            for pid, data in self._data.persons.items():
                if data.get("pseudo") == person:
                    person_ids.append(pid)

        self._data.set_persons_home(person_ids=person_ids, home_id=self._home_id)
        _LOGGER.debug("Set %s as at home", persons)

    def _service_set_person_away(self, **kwargs):
        """Service to mark a person as away or set the home as empty."""
        person = kwargs.get(ATTR_PERSON)
        person_id = None
        if person:
            for pid, data in self._data.persons.items():
                if data.get("pseudo") == person:
                    person_id = pid

        if person_id is not None:
            self._data.set_persons_away(
                person_id=person_id,
                home_id=self._home_id,
            )
            _LOGGER.debug("Set %s as away", person)

        else:
            self._data.set_persons_away(
                person_id=person_id,
                home_id=self._home_id,
            )
            _LOGGER.debug("Set home as empty")

    def _service_set_camera_light(self, **kwargs):
        """Service to set light mode."""
        mode = kwargs.get(ATTR_CAMERA_LIGHT_MODE)
        _LOGGER.debug("Turn camera '%s' %s", self._name, mode)
        self._data.set_state(
            home_id=self._home_id,
            camera_id=self._id,
            floodlight=mode,
        )
