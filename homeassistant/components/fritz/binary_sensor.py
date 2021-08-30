"""AVM FRITZ!Box connectivity sensor."""
from __future__ import annotations

import logging
from typing import Callable, TypedDict

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PLUG,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import FritzBoxBaseEntity, FritzBoxTools
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _retrieve_connection_state(status: FritzStatus) -> bool:
    """Return download line attenuation."""
    return bool(status.is_connected)


def _retrieve_link_state(status: FritzStatus) -> bool:
    """Return download line attenuation."""
    return bool(status.is_linked)


class SensorData(TypedDict):
    """Sensor data class."""

    name: str
    device_class: str | None
    state_provider: Callable


SENSOR_DATA = {
    "is_connected": SensorData(
        name="Connection",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        state_provider=_retrieve_connection_state,
    ),
    "is_linked": SensorData(
        name="Link",
        device_class=DEVICE_CLASS_PLUG,
        state_provider=_retrieve_link_state,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box binary sensors")
    fritzbox_tools: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]

    if (
        not fritzbox_tools.connection
        or "WANIPConn1" not in fritzbox_tools.connection.services
    ):
        # Only routers are supported at the moment
        return

    entities = []
    for sensor_type in SENSOR_DATA:
        entities.append(FritzBoxBinarySensor(fritzbox_tools, entry.title, sensor_type))

    if entities:
        async_add_entities(entities, True)


class FritzBoxBinarySensor(FritzBoxBaseEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self, fritzbox_tools: FritzBoxTools, device_friendly_name: str, sensor_type: str
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self._sensor_data: SensorData = SENSOR_DATA[sensor_type]
        self._attr_available = True
        self._attr_device_class = self._sensor_data.get("device_class")
        self._attr_name = f"{device_friendly_name} {self._sensor_data['name']}"
        self._attr_unique_id = f"{fritzbox_tools.unique_id}-{sensor_type}"
        super().__init__(fritzbox_tools, device_friendly_name)

    @property
    def _state_provider(self) -> Callable:
        """Return the state provider for the binary sensor."""
        return self._sensor_data["state_provider"]

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box binary sensors")

        try:
            status: FritzStatus = self._fritzbox_tools.fritz_status
            self._attr_available = True
        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._attr_available = False
            return

        self._attr_is_on = self._state_provider(status)
