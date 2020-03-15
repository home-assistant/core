"""Support for August sensors."""
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY, DEVICE_CLASS_POWER

from . import PowerWallEntity
from .const import (
    ATTR_ENERGY_EXPORTED,
    ATTR_ENERGY_IMPORTED,
    ATTR_FREQUENCY,
    ATTR_INSTANT_AVERAGE_VOLTAGE,
    DOMAIN,
    POWERWALL_API_CHARGE,
    POWERWALL_API_METERS,
    POWERWALL_COORDINATOR,
    POWERWALL_IP_ADDRESS,
    POWERWALL_SITE_INFO,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    powerwall_data = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Powerwall_data: %s", powerwall_data)

    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    site_info = powerwall_data[POWERWALL_SITE_INFO]
    ip_address = powerwall_data[POWERWALL_IP_ADDRESS]

    entities = []
    for meter in coordinator.data[POWERWALL_API_METERS]:
        entities.append(
            PowerWallEnergySensor(meter, coordinator, site_info, ip_address)
        )

    entities.append(PowerWallChargeSensor(coordinator, site_info, ip_address))

    async_add_entities(entities, True)


class PowerWallSensor(PowerWallEntity):
    """Base class for powerwall sensors."""

    def __init__(self, coordinator, site_info, ip_address):
        """Initialize the sensor."""
        super().__init__(coordinator, site_info, ip_address)
        self._coordinator = coordinator

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)


class PowerWallChargeSensor(PowerWallSensor):
    """Representation of an Powerwall charge sensor."""

    def __init__(self, coordinator, site_info, ip_address):
        """Initialize the sensor."""
        super().__init__(coordinator, site_info, ip_address)
        self._coordinator = coordinator
        self._site_info = site_info
        self._ip_address = ip_address

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"  # switch to UNIT_PERCENTAGE

    @property
    def name(self):
        """Device Name."""
        return "Powerwall Charge"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self._ip_address}_charge"

    @property
    def state(self):
        """Get the current value in percentage."""
        return round(self._coordinator.data[POWERWALL_API_CHARGE], 3)


class PowerWallEnergySensor(PowerWallSensor):
    """Representation of an Powerwall Energy sensor."""

    def __init__(self, meter, coordinator, site_info, ip_address):
        """Initialize the sensor."""
        super().__init__(coordinator, site_info, ip_address)
        self._coordinator = coordinator
        self._meter = meter
        self._site_info = site_info
        self._ip_address = ip_address

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "kWh"

    @property
    def name(self):
        """Device Name."""
        return f"Powerwall {self._meter.title()} Now"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_POWER

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self._ip_address}_{self._meter}_instant_power"

    @property
    def state(self):
        """Get the current value in kWh."""
        meter = self._coordinator.data[POWERWALL_API_METERS][self._meter]
        return round(float(meter.instant_power / 1000), 3)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        meter = self._coordinator.data[POWERWALL_API_METERS][self._meter]
        return {
            ATTR_FREQUENCY: meter.frequency,
            ATTR_ENERGY_EXPORTED: meter.energy_exported,
            ATTR_ENERGY_IMPORTED: meter.energy_imported,
            ATTR_INSTANT_AVERAGE_VOLTAGE: meter.instant_average_voltage,
        }
