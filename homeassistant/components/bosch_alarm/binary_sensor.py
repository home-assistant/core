"""Support for Bosch Alarm Panel binary sensors."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for alarm points and the connection status."""
    panel = config_entry.runtime_data

    async_add_entities(
        PointSensor(panel, point_id, config_entry.unique_id or config_entry.entry_id)
        for point_id in panel.points
    )


PARALLEL_UPDATES = 0


class PointSensor(BinarySensorEntity):
    """A binary sensor entity for a point in a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, panel: Panel, point_id: int, unique_id: str) -> None:
        """Set up a binary sensor entity for a point in a bosch alarm panel."""
        self.panel = panel
        self._attr_unique_id = f"{unique_id}_point_{point_id}"
        self._point = panel.points[point_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Bosch Security Systems",
            name=self._point.name,
            via_device=(DOMAIN, unique_id),
        )

    @property
    def is_on(self) -> bool:
        """Return if this point sensor is on."""
        return self._point.is_open()

    @property
    def available(self) -> bool:
        """Return if this point sensor is available."""
        return self._point.is_open() or self._point.is_normal()

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        await super().async_added_to_hass()
        self._point.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        self._point.status_observer.detach(self.schedule_update_ha_state)
