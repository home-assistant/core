"""Support for the Netatmo camera lights."""
import logging

import pyatmo

from homeassistant.components.light import LightEntity
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady

from .const import DATA_HANDLER, DOMAIN, MANUFACTURER, SIGNAL_NAME
from .data_handler import CAMERA_DATA_CLASS_NAME, NetatmoDataHandler
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo camera light platform."""
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

        entities = []
        try:
            all_cameras = []
            for home in data_handler.data[CAMERA_DATA_CLASS_NAME].cameras.values():
                for camera in home.values():
                    all_cameras.append(camera)

            for camera in all_cameras:
                if camera["type"] == "NOC":
                    if not data_handler.webhook:
                        raise PlatformNotReady

                    _LOGGER.debug(
                        "Adding camera light %s %s", camera["id"], camera["name"]
                    )
                    entities.append(
                        NetatmoLight(
                            data_handler,
                            camera["id"],
                            camera["type"],
                            camera["home_id"],
                        )
                    )

        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")

        return entities

    async_add_entities(await get_entities(), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo camera platform."""
    return


class NetatmoLight(NetatmoBase, LightEntity):
    """Representation of a Netatmo Presence camera light."""

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        camera_id: str,
        camera_type: str,
        home_id: str,
    ):
        """Initialize a Netatmo Presence camera light."""
        LightEntity.__init__(self)
        super().__init__(data_handler)

        self._data_classes.append(
            {"name": CAMERA_DATA_CLASS_NAME, SIGNAL_NAME: CAMERA_DATA_CLASS_NAME}
        )
        self._id = camera_id
        self._home_id = home_id
        self._model = camera_type
        self._device_name = self._data.get_camera(camera_id).get("name")
        self._name = f"{MANUFACTURER} {self._device_name}"
        self._is_on = False
        self._unique_id = f"{self._id}-light"

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self._listeners.append(
            self.hass.bus.async_listen("netatmo_event", self.handle_event)
        )

    async def handle_event(self, event):
        """Handle webhook events."""
        data = event.data["data"]

        if not data.get("event_type"):
            return

        if not data.get("camera_id"):
            return

        if (
            data["home_id"] == self._home_id
            and data["camera_id"] == self._id
            and data["push_type"] == "NOC-light_mode"
        ):
            self._is_on = bool(data["sub_type"] == "on")

            self.async_write_ha_state()
            return

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self._name)
        self._data.set_state(
            home_id=self._home_id, camera_id=self._id, floodlight="on",
        )

    def turn_off(self, **kwargs):
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' off", self._name)
        self._data.set_state(
            home_id=self._home_id, camera_id=self._id, floodlight="auto",
        )

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        self._is_on = bool(self._data.get_light_state(self._id) == "on")
