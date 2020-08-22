"""Support for Risco alarm zones."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)

from .const import DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Risco alarm control panel."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = [
        RiscoBinarySensor(hass, coordinator, zone_id, zone)
        for zone_id, zone in coordinator.data.zones.items()
    ]

    async_add_entities(entities, False)


class RiscoBinarySensor(BinarySensorEntity):
    """Representation of a Risco zone as a binary sensor."""

    def __init__(self, hass, coordinator, zone_id, zone):
        """Init the zone."""
        self._hass = hass
        self._coordinator = coordinator
        self._zone_id = zone_id
        self._zone = zone

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    def _refresh_from_coordinator(self):
        self._zone = self._coordinator.data.zones[self._zone_id]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._refresh_from_coordinator)
        )

    @property
    def _risco(self):
        """Return the Risco API object."""
        return self._coordinator.risco

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Risco",
        }

    @property
    def name(self):
        """Return the name of the zone."""
        return self._zone.name

    @property
    def unique_id(self):
        """Return a unique id for this zone."""
        return f"{self._risco.site_uuid}_{self._zone_id}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"bypassed": self._zone.bypassed}

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._zone.triggered

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return DEVICE_CLASS_MOTION
