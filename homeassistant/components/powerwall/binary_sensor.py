"""Support for August sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorDevice,
)
from homeassistant.const import DEVICE_CLASS_POWER

from .const import (
    ATTR_GRID_CODE,
    ATTR_NOMINAL_SYSTEM_POWER,
    ATTR_REGION,
    DOMAIN,
    POWERWALL_API_GRID_STATUS,
    POWERWALL_API_SITEMASTER,
    POWERWALL_CONNECTED_KEY,
    POWERWALL_COORDINATOR,
    POWERWALL_GRID_ONLINE,
    POWERWALL_RUNNING_KEY,
    POWERWALL_SITE_INFO,
    SITE_INFO_GRID_CODE,
    SITE_INFO_NOMINAL_SYSTEM_POWER_KW,
    SITE_INFO_REGION,
)
from .entity import PowerWallEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    powerwall_data = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    site_info = powerwall_data[POWERWALL_SITE_INFO]

    entities = []
    for sensor_class in (
        PowerWallRunningSensor,
        PowerWallGridStatusSensor,
        PowerWallConnectedSensor,
    ):
        entities.append(sensor_class(coordinator, site_info))

    async_add_entities(entities, True)


class PowerWallRunningSensor(PowerWallEntity, BinarySensorDevice):
    """Representation of an Powerwall running sensor."""

    @property
    def name(self):
        """Device Name."""
        return "Powerwall Status"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_POWER

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_running"

    @property
    def is_on(self):
        """Get the powerwall running state."""
        return self._coordinator.data[POWERWALL_API_SITEMASTER][POWERWALL_RUNNING_KEY]

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_REGION: self._site_info[SITE_INFO_REGION],
            ATTR_GRID_CODE: self._site_info[SITE_INFO_GRID_CODE],
            ATTR_NOMINAL_SYSTEM_POWER: self._site_info[
                SITE_INFO_NOMINAL_SYSTEM_POWER_KW
            ],
        }


class PowerWallConnectedSensor(PowerWallEntity, BinarySensorDevice):
    """Representation of an Powerwall connected sensor."""

    @property
    def name(self):
        """Device Name."""
        return "Powerwall Connected to Tesla"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_connected_to_tesla"

    @property
    def is_on(self):
        """Get the powerwall connected to tesla state."""
        return self._coordinator.data[POWERWALL_API_SITEMASTER][POWERWALL_CONNECTED_KEY]


class PowerWallGridStatusSensor(PowerWallEntity, BinarySensorDevice):
    """Representation of an Powerwall grid status sensor."""

    @property
    def name(self):
        """Device Name."""
        return "Grid Status"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_POWER

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_grid_status"

    @property
    def is_on(self):
        """Get the current value in kWh."""
        return (
            self._coordinator.data[POWERWALL_API_GRID_STATUS] == POWERWALL_GRID_ONLINE
        )
