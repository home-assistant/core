"""Support for Freebox binary sensors (motion sensor, door opener and plastic cover)."""
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .home_base import FreeboxHomeEntity
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    tracked: set = set()
    new_trackedpir = []
    new_trackeddws = []
    new_trackedcover = []

    for nodeid, node in router.home_devices.items():
        if nodeid in tracked:
            continue
        if node["category"] == "pir":
            new_trackedpir.append(FreeboxPir(hass, router, node))
        elif node["category"] == "dws":
            new_trackeddws.append(FreeboxDws(hass, router, node))

        sensor_cover_node = next(
            filter(
                lambda x: (x["name"] == "cover" and x["ep_type"] == "signal"),
                node["show_endpoints"],
            ),
            None,
        )
        if sensor_cover_node and sensor_cover_node.get("value") is not None:
            new_trackedcover.append(FreeboxSensorCover(hass, router, node))

        tracked.add(nodeid)

    if new_trackedpir:
        async_add_entities(new_trackedpir, True)
    if new_trackeddws:
        async_add_entities(new_trackeddws, True)
    if new_trackedcover:
        async_add_entities(new_trackedcover, True)


class FreeboxPir(FreeboxHomeEntity, BinarySensorEntity):
    """Representation of a Freebox motion binary sensor."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a Pir."""
        super().__init__(hass, router, node)
        self._command_trigger = self.get_command_id(
            node["type"]["endpoints"], "signal", "trigger"
        )

        self._detection = False
        self._had_timeout = False

    async def async_update_signal(self):
        """Watch states."""
        try:
            detection = await self.get_home_endpoint_value(self._command_trigger)
            self._had_timeout = False
            if self._detection == detection:
                self._detection = not detection
                self.async_write_ha_state()
        except TimeoutError as error:
            if self._had_timeout:
                _LOGGER.warning("Freebox API Timeout. %s", error)
                self._had_timeout = False
            else:
                self._had_timeout = True

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._detection

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.MOTION


class FreeboxDws(FreeboxPir):
    """Representation of a Freebox door opener binary sensor."""

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.DOOR


class FreeboxSensorCover(FreeboxHomeEntity, BinarySensorEntity):
    """Representation of a cover Freebox plastic removal cover binary sensor (for some sensors: motion detector, door opener detector...)."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a cover for another device."""
        # Get cover node
        cover_node = next(
            filter(
                lambda x: (x["name"] == "cover" and x["ep_type"] == "signal"),
                node["type"]["endpoints"],
            ),
            None,
        )
        super().__init__(hass, router, node, cover_node)
        self._command_cover = self.get_command_id(
            node["type"]["endpoints"], "signal", "cover"
        )
        self._open = self.get_value("signal", "cover")

    @property
    def is_on(self) -> None:
        """Return true if the binary sensor is on."""
        return self._open

    async def async_update_node(self):
        """Update name & state."""
        self._open = self.get_value("signal", "cover")

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.SAFETY
