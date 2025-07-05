"""Support for Velux covers."""

from __future__ import annotations

from pyvlx.exception import PyVLXException
from pyvlx.opening_device import OpeningDevice, Window

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER
from .entity import VeluxEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rain sensor(s) for Velux platform."""
    module = hass.data[DOMAIN][config.entry_id]

    entities = [
        VeluxRainSensor(node, hass, config.entry_id)
        for node in module.pyvlx.nodes
        if isinstance(node, Window) and node.rain_sensor
    ]

    for entity in entities:
        await entity.coordinator.async_config_entry_first_refresh()

    async_add_entities(entities)


class VeluxRainSensor(VeluxEntity, BinarySensorEntity):
    """Representation of a Velux rain sensor."""

    node: Window

    def __init__(
        self, node: OpeningDevice, hass: HomeAssistant, config_entry_id: str
    ) -> None:
        """Initialize VeluxRainSensor."""
        super().__init__(node, config_entry_id)
        self._hass = hass
        self._attr_unique_id = f"{self._attr_unique_id}_rain_sensor"
        self._attr_name = f"{node.name} Rain Sensor"
        LOGGER.info("Creating velux rain sensor from %s", node.name)
        self._attr_device_class = BinarySensorDeviceClass.MOISTURE
        self.rain_detected = False
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOGGER,
            name=self._attr_unique_id,
            update_method=self.async_update_rain_sensor,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def async_update_rain_sensor(self):
        """Get the updated status of the cover (limitations only)."""
        try:
            limitation = await self.node.get_limitation()
            self.rain_detected = limitation.min_value == 93
            LOGGER.info(
                f"Rain sensor updated, limitation max/min_value={limitation.max_value}/{limitation.min_value} raw max/min_value={limitation.max_value_raw}/{limitation.min_value_raw}"
            )
        except PyVLXException:
            LOGGER.error("Error fetch limitation data for cover %s", self.name)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return if the rain sensor is triggered."""
        return self.rain_detected
