"""Elmax sensor platform."""
from __future__ import annotations

from elmax_api.model.panel import PanelStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElmaxCoordinator
from .common import ElmaxEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Elmax sensor platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status: PanelStatus = coordinator.data
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = []
        for zone in panel_status.zones:
            # Skip already handled devices
            if zone.endpoint_id in known_devices:
                continue
            entity = ElmaxSensor(
                panel=coordinator.panel_entry,
                elmax_device=zone,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            entities.append(entity)

        if entities:
            async_add_entities(entities)
            known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    remove_handle = coordinator.async_add_listener(_discover_new_devices)
    config_entry.async_on_unload(remove_handle)

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()


class ElmaxSensor(ElmaxEntity, BinarySensorEntity):
    """Elmax Sensor entity implementation."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.get_zone_state(self._device.endpoint_id).opened
