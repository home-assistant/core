"""Support for Bosch Alarm Panel points as binary sensors."""

from __future__ import annotations

import logging
import re

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


def _guess_device_class(name):
    if re.search(r"\b(win(d)?(ow)?|wn)\b", name):
        return BinarySensorDeviceClass.WINDOW
    if re.search(r"\b(door|dr)\b", name):
        return BinarySensorDeviceClass.DOOR
    if re.search(r"\b(motion|md)\b", name):
        return BinarySensorDeviceClass.MOTION
    if re.search(r"\bco\b", name):
        return BinarySensorDeviceClass.CO
    if re.search(r"\bsmoke\b", name):
        return BinarySensorDeviceClass.SMOKE
    if re.search(r"\bglassbr(ea)?k\b", name):
        return BinarySensorDeviceClass.TAMPER
    return None


class PanelBinarySensor(BinarySensorEntity):
    """A binary sensor entity for a bosch alarm panel."""

    def __init__(self, observer, unique_id, device_info) -> None:
        """Initialise a binary sensor entity for a bosch alarm panel."""
        self._observer = observer
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        self._observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Set the date and time on a bosch alarm panel."""
        self._observer.detach(self.schedule_update_ha_state)


class PointSensor(PanelBinarySensor):
    """A binary sensor entity for a point in a bosch alarm panel."""

    def __init__(self, point, unique_id, device_info) -> None:
        """Set up a binary sensor entity for a point in a bosch alarm panel."""
        PanelBinarySensor.__init__(self, point.status_observer, unique_id, device_info)
        self._point = point

    @property
    def name(self) -> str:
        """Return the name of this point sensor."""
        return self._point.name

    @property
    def is_on(self) -> bool:
        """Return if this point sensor is on."""
        return self._point.is_open()

    @property
    def available(self) -> bool:
        """Return if this point sensor is available."""
        return self._point.is_open() or self._point.is_normal()

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return a guess for the device class for this point sensor."""
        return _guess_device_class(self.name.lower())


class ConnectionStatusSensor(PanelBinarySensor):
    """A binary sensor entity for the connection status in a bosch alarm panel."""

    def __init__(self, panel_conn, unique_id) -> None:
        """Set up a binary sensor entity for the connection status in a bosch alarm panel."""
        PanelBinarySensor.__init__(
            self,
            panel_conn.panel.connection_status_observer,
            unique_id,
            panel_conn.device_info(),
        )
        self._panel = panel_conn.panel

    @property
    def name(self) -> str:
        """Return the name of this connection status sensor."""
        return "Connection Status"

    @property
    def is_on(self) -> bool:
        """Return if this panel is connected."""
        return self._panel.connection_status()

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class for this sensor."""
        return BinarySensorDeviceClass.CONNECTIVITY


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for alarm points and the connection status."""

    panel_conn = config_entry.runtime_data
    panel = panel_conn.panel

    async_add_entities(
        [
            ConnectionStatusSensor(
                panel_conn, f"{panel_conn.unique_id}_connection_status"
            )
        ]
    )

    async_add_entities(
        PointSensor(
            point,
            f"{panel_conn.unique_id}_point_{point_id}",
            panel_conn.device_info(),
        )
        for (point_id, point) in panel.points.items()
    )
