"""Support for the Netatmo cameras."""
from __future__ import annotations

import logging
from typing import Any, cast

import aiohttp
import pyatmo
import voluptuous as vol

from homeassistant.components.camera import SUPPORT_STREAM, Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    EVENT_TYPE_LIGHT_MODE,
    EVENT_TYPE_OFF,
    EVENT_TYPE_ON,
    MANUFACTURER,
    MODELS,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
    SIGNAL_NAME,
    WEBHOOK_LIGHT_MODE,
    WEBHOOK_NACAMERA_CONNECTION,
    WEBHOOK_PUSH_TYPE,
)
from .data_handler import CAMERA_DATA_CLASS_NAME, NetatmoDataHandler
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)

DEFAULT_QUALITY = "high"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo camera platform."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    await data_handler.register_data_class(
        CAMERA_DATA_CLASS_NAME, CAMERA_DATA_CLASS_NAME, None
    )
    data_class = data_handler.data.get(CAMERA_DATA_CLASS_NAME)

    if not data_class or not data_class.raw_data:
        raise PlatformNotReady

    all_cameras = []
    for home in data_class.cameras.values():
        for camera in home.values():
            all_cameras.append(camera)

    entities = [
        NetatmoCamera(
            data_handler,
            camera["id"],
            camera["type"],
            camera["home_id"],
            DEFAULT_QUALITY,
        )
        for camera in all_cameras
    ]

    for home in data_class.homes.values():
        if home.get("id") is None:
            continue

        hass.data[DOMAIN][DATA_PERSONS][home["id"]] = {
            person_id: person_data.get(ATTR_PSEUDO)
            for person_id, person_data in data_handler.data[CAMERA_DATA_CLASS_NAME]
            .persons[home["id"]]
            .items()
        }

    _LOGGER.debug("Adding cameras %s", entities)
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

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
        data_handler: NetatmoDataHandler,
        camera_id: str,
        camera_type: str,
        home_id: str,
        quality: str,
    ) -> None:
        """Set up for access to the Netatmo camera images."""
        Camera.__init__(self)
        super().__init__(data_handler)

        self._data_classes.append(
            {"name": CAMERA_DATA_CLASS_NAME, SIGNAL_NAME: CAMERA_DATA_CLASS_NAME}
        )

        self._id = camera_id
        self._home_id = home_id
        self._device_name = self._data.get_camera(camera_id=camera_id)["name"]
        self._attr_name = f"{MANUFACTURER} {self._device_name}"
        self._model = camera_type
        self._attr_unique_id = f"{self._id}-{self._model}"
        self._quality = quality
        self._vpnurl: str | None = None
        self._localurl: str | None = None
        self._status: str | None = None
        self._sd_status: str | None = None
        self._alim_status: str | None = None
        self._is_local: str | None = None
        self._light_state = None

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        for event_type in (EVENT_TYPE_LIGHT_MODE, EVENT_TYPE_OFF, EVENT_TYPE_ON):
            self._listeners.append(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )

        self.hass.data[DOMAIN][DATA_CAMERAS][self._id] = self._device_name

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if not data.get("camera_id"):
            return

        if data["home_id"] == self._home_id and data["camera_id"] == self._id:
            if data[WEBHOOK_PUSH_TYPE] in ("NACamera-off", "NACamera-disconnection"):
                self.is_streaming = False
                self._status = "off"
            elif data[WEBHOOK_PUSH_TYPE] in (
                "NACamera-on",
                WEBHOOK_NACAMERA_CONNECTION,
            ):
                self.is_streaming = True
                self._status = "on"
            elif data[WEBHOOK_PUSH_TYPE] == WEBHOOK_LIGHT_MODE:
                self._light_state = data["sub_type"]
                self._attr_extra_state_attributes.update(
                    {"light_state": self._light_state}
                )

            self.async_write_ha_state()
            return

    @property
    def _data(self) -> pyatmo.AsyncCameraData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncCameraData,
            self.data_handler.data[self._data_classes[0]["name"]],
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            return cast(
                bytes, await self._data.async_get_live_snapshot(camera_id=self._id)
            )
        except (
            aiohttp.ClientPayloadError,
            aiohttp.ContentTypeError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientConnectorError,
            pyatmo.exceptions.ApiError,
        ) as err:
            _LOGGER.debug("Could not fetch live camera image (%s)", err)
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._alim_status == "on" or self._status == "disconnected")

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return SUPPORT_STREAM

    @property
    def brand(self) -> str:
        """Return the camera brand."""
        return MANUFACTURER

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return bool(self._status == "on")

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self.is_streaming

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self._data.async_set_state(
            home_id=self._home_id, camera_id=self._id, monitoring="off"
        )

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self._data.async_set_state(
            home_id=self._home_id, camera_id=self._id, monitoring="on"
        )

    async def stream_source(self) -> str:
        """Return the stream source."""
        url = "{0}/live/files/{1}/index.m3u8"
        if self._localurl:
            return url.format(self._localurl, self._quality)
        return url.format(self._vpnurl, self._quality)

    @property
    def model(self) -> str:
        """Return the camera model."""
        return MODELS[self._model]

    @callback
    def async_update_callback(self) -> None:
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

        self._attr_extra_state_attributes.update(
            {
                "id": self._id,
                "status": self._status,
                "sd_status": self._sd_status,
                "alim_status": self._alim_status,
                "is_local": self._is_local,
                "vpn_url": self._vpnurl,
                "local_url": self._localurl,
                "light_state": self._light_state,
            }
        )

    def process_events(self, events: dict) -> dict:
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

    def fetch_person_ids(self, persons: list[str | None]) -> list[str]:
        """Fetch matching person ids for give list of persons."""
        person_ids = []
        person_id_errors = []

        for person in persons:
            person_id = None
            for pid, data in self._data.persons[self._home_id].items():
                if data.get("pseudo") == person:
                    person_ids.append(pid)
                    person_id = pid
                    break

            if person_id is None:
                person_id_errors.append(person)

        if person_id_errors:
            raise HomeAssistantError(f"Person(s) not registered {person_id_errors}")

        return person_ids

    async def _service_set_persons_home(self, **kwargs: Any) -> None:
        """Service to change current home schedule."""
        persons = kwargs.get(ATTR_PERSONS, [])
        person_ids = self.fetch_person_ids(persons)

        await self._data.async_set_persons_home(
            person_ids=person_ids, home_id=self._home_id
        )
        _LOGGER.debug("Set %s as at home", persons)

    async def _service_set_person_away(self, **kwargs: Any) -> None:
        """Service to mark a person as away or set the home as empty."""
        person = kwargs.get(ATTR_PERSON)
        person_ids = self.fetch_person_ids([person] if person else [])
        person_id = next(iter(person_ids), None)

        await self._data.async_set_persons_away(
            person_id=person_id,
            home_id=self._home_id,
        )

        if person_id:
            _LOGGER.debug("Set %s as away %s", person, person_id)
        else:
            _LOGGER.debug("Set home as empty")

    async def _service_set_camera_light(self, **kwargs: Any) -> None:
        """Service to set light mode."""
        mode = str(kwargs.get(ATTR_CAMERA_LIGHT_MODE))
        _LOGGER.debug("Turn %s camera light for '%s'", mode, self._attr_name)
        await self._data.async_set_state(
            home_id=self._home_id,
            camera_id=self._id,
            floodlight=mode,
        )
