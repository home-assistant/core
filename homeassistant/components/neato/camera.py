"""Support for loading picture from Neato."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pybotvac.exceptions import NeatoRobotException
from pybotvac.robot import Robot
from urllib3.response import HTTPResponse

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_LOGIN, NEATO_MAP_DATA, NEATO_ROBOTS, SCAN_INTERVAL_MINUTES
from .entity import NeatoEntity
from .hub import NeatoHub

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)
ATTR_GENERATED_AT = "generated_at"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato camera with config entry."""
    dev = []
    neato: NeatoHub = hass.data[NEATO_LOGIN]
    mapdata: dict[str, Any] | None = hass.data.get(NEATO_MAP_DATA)
    for robot in hass.data[NEATO_ROBOTS]:
        if "maps" in robot.traits:
            dev.append(NeatoCleaningMap(neato, robot, mapdata))

    if not dev:
        return

    _LOGGER.debug("Adding robots for cleaning maps %s", dev)
    async_add_entities(dev, True)


class NeatoCleaningMap(NeatoEntity, Camera):
    """Neato cleaning map for last clean."""

    _attr_translation_key = "cleaning_map"

    def __init__(
        self, neato: NeatoHub, robot: Robot, mapdata: dict[str, Any] | None
    ) -> None:
        """Initialize Neato cleaning map."""
        super().__init__(robot)
        Camera.__init__(self)
        self.neato = neato
        self._mapdata = mapdata
        self._available = neato is not None
        self._robot_serial: str = self.robot.serial
        self._generated_at: str | None = None
        self._image_url: str | None = None
        self._image: bytes | None = None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        self.update()
        return self._image

    def update(self) -> None:
        """Check the contents of the map list."""

        _LOGGER.debug("Running camera update for '%s'", self.entity_id)
        try:
            self.neato.update_robots()
        except NeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._image_url = None
            self._available = False
            return

        if self._mapdata:
            map_data: dict[str, Any] = self._mapdata[self._robot_serial]["maps"][0]
        if (image_url := map_data["url"]) == self._image_url:
            _LOGGER.debug(
                "The map image_url for '%s' is the same as old", self.entity_id
            )
            return

        try:
            image: HTTPResponse = self.neato.download_map(image_url)
        except NeatoRobotException as ex:
            if self._available:  # Print only once when available
                _LOGGER.error(
                    "Neato camera connection error for '%s': %s", self.entity_id, ex
                )
            self._image = None
            self._image_url = None
            self._available = False
            return

        self._image = image.read()
        self._image_url = image_url
        self._generated_at = map_data.get("generated_at")
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._robot_serial

    @property
    def available(self) -> bool:
        """Return if the robot is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}

        if self._generated_at is not None:
            data[ATTR_GENERATED_AT] = self._generated_at

        return data
