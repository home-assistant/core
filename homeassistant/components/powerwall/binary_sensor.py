"""Support for powerwall binary sensors."""
import logging

from tesla_powerwall import GridStatus

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.const import DEVICE_CLASS_POWER

from .const import (
    DOMAIN,
    POWERWALL_API_DEVICE_TYPE,
    POWERWALL_API_GRID_STATUS,
    POWERWALL_API_METERS,
    POWERWALL_API_SERIAL_NUMBERS,
    POWERWALL_API_SITE_INFO,
    POWERWALL_API_SITEMASTER,
    POWERWALL_API_STATUS,
    POWERWALL_BATTERY_METER,
    POWERWALL_COORDINATOR,
)
from .entity import PowerWallEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the August sensors."""
    powerwall_data = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    site_info = powerwall_data[POWERWALL_API_SITE_INFO]
    device_type = powerwall_data[POWERWALL_API_DEVICE_TYPE]
    status = powerwall_data[POWERWALL_API_STATUS]
    powerwalls_serial_numbers = powerwall_data[POWERWALL_API_SERIAL_NUMBERS]

    entities = []
    for sensor_class in (
        PowerWallRunningSensor,
        PowerWallGridStatusSensor,
        PowerWallConnectedSensor,
        PowerWallChargingStatusSensor,
    ):
        entities.append(
            sensor_class(
                coordinator, site_info, status, device_type, powerwalls_serial_numbers
            )
        )

    async_add_entities(entities, True)


class PowerWallRunningSensor(PowerWallEntity, BinarySensorEntity):
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
        return self.coordinator.data[POWERWALL_API_SITEMASTER].running


class PowerWallConnectedSensor(PowerWallEntity, BinarySensorEntity):
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
        return self.coordinator.data[POWERWALL_API_SITEMASTER].connected_to_tesla


class PowerWallGridStatusSensor(PowerWallEntity, BinarySensorEntity):
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
        """Grid is online."""
        return self.coordinator.data[POWERWALL_API_GRID_STATUS] == GridStatus.CONNECTED


class PowerWallChargingStatusSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of an Powerwall charging status sensor."""

    @property
    def name(self):
        """Device Name."""
        return "Powerwall Charging"

    @property
    def device_class(self):
        """Device Class."""
        return DEVICE_CLASS_BATTERY_CHARGING

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return f"{self.base_unique_id}_powerwall_charging"

    @property
    def is_on(self):
        """Powerwall is charging."""
        # is_sending_to returns true for values greater than 100 watts
        return self.coordinator.data[POWERWALL_API_METERS][
            POWERWALL_BATTERY_METER
        ].is_sending_to()
