"""Base entity class for Pax Calima integration."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
 
class PaxCalimaEntity(CoordinatorEntity):
    """Pax Calima base entity class."""

    def __init__(self, coordinator, sensor):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        """Generic Entity properties"""
        self._attr_entity_category = sensor.category        
        self._attr_name = '{} {}'.format(self.coordinator.devicename, sensor.entityName)
        self._attr_unique_id = '{}-{}'.format(self.coordinator.mac, self.name)
        self._attr_device_info = {
            "identifiers": { (DOMAIN, self.coordinator.mac) },
            "name": self.coordinator.devicename,
            "manufacturer": self.coordinator.get_data('manufacturer'),
            "model": self.coordinator.get_data('model'),    
            "hw_version": self.coordinator.get_data('hw_rev'),
            "sw_version": self.coordinator.get_data('sw_rev'),
        }
        
        """Store this entities key."""
        self._key = sensor.key
