"""Support for Risco alarm zones."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)
from homeassistant.helpers import entity_platform

from .const import DATA_COORDINATOR, DOMAIN
from .entity import RiscoEntity

SERVICE_BYPASS_ZONE = "bypass_zone"
SERVICE_UNBYPASS_ZONE = "unbypass_zone"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Risco alarm control panel."""
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(SERVICE_BYPASS_ZONE, {}, "async_bypass_zone")
    platform.async_register_entity_service(
        SERVICE_UNBYPASS_ZONE, {}, "async_unbypass_zone"
    )

    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = [
        RiscoBinarySensor(coordinator, zone_id, zone)
        for zone_id, zone in coordinator.data.zones.items()
    ]

    async_add_entities(entities, False)


class RiscoBinarySensor(BinarySensorEntity, RiscoEntity):
    """Representation of a Risco zone as a binary sensor."""

    def __init__(self, coordinator, zone_id, zone):
        """Init the zone."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._zone = zone

    def _get_data_from_coordinator(self):
        self._zone = self._coordinator.data.zones[self._zone_id]

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
        return f"{self._risco.site_uuid}_zone_{self._zone_id}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"bypassed": self._zone.bypassed}

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._zone.triggered

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return DEVICE_CLASS_MOTION

    async def _bypass(self, bypass):
        alarm = await self._risco.bypass_zone(self._zone_id, bypass)
        self._zone = alarm.zones[self._zone_id]
        self.async_write_ha_state()

    async def async_bypass_zone(self):
        """Bypass this zone."""
        await self._bypass(True)

    async def async_unbypass_zone(self):
        """Unbypass this zone."""
        await self._bypass(False)
