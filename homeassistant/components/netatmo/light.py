"""Support for the Netatmo camera lights."""
import logging

import pyatmo

from homeassistant.components.light import Light
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady

from .const import DATA_HANDLER, DOMAIN, MANUFACTURER
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

    if not data_handler.webhook:
        raise PlatformNotReady

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
                if camera["type"] == "NOC":
                    _LOGGER.debug(
                        "Adding camera light %s %s", camera["id"], camera["name"]
                    )
                    entities.append(
                        NetatmoLight(
                            data_handler,
                            data_class,
                            camera["id"],
                            camera["type"],
                            camera["home_id"],
                        )
                    )

        except pyatmo.NoDevice:
            _LOGGER.debug("No cameras found")

        await data_handler.unregister_data_class(data_class)
        return entities

    async_add_entities(await get_entities(), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo camera platform."""
    return


class NetatmoLight(Light, NetatmoBase):
    """Representation of a Netatmo Presence camera light."""

    def __init__(
        self, data_handler, data_class, camera_id: str, camera_type: str, home_id: str
    ):
        """Initialize a Netatmo Presence camera light."""
        Light.__init__(self)
        NetatmoBase.__init__(self, data_handler)

        self._data_classes.append({"name": data_class})
        self._camera_id = camera_id
        self._home_id = home_id
        self._camera_type = camera_type
        self._name = f"{MANUFACTURER} {self._data.get_camera(camera_id).get('name')}"
        self._is_on = False
        self._unique_id = f"{self._camera_id}-light"

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
                and data["push_type"] == "NOC-light_mode"
            ):
                if data["sub_type"] in ["off", "auto"]:
                    self._is_on = False

                elif data["sub_type"] == "on":
                    self._is_on = True

                self.schedule_update_ha_state()
                return

        self.hass.bus.async_listen("netatmo_event", handle_event)

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
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self._name)
        self._data.set_state(
            home_id=self._home_id, camera_id=self._camera_id, floodlight="on",
        )

    def turn_off(self, **kwargs):
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' off", self._name)
        self._data.set_state(
            home_id=self._home_id, camera_id=self._camera_id, floodlight="auto",
        )

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        if self._data.get_light_state(self._camera_id) == "on":
            self._is_on = True
        else:
            self._is_on = False
