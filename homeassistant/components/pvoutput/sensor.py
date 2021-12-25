"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from datetime import timedelta
import logging

from pvo import PVOutput, PVOutputError, Status
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    CONF_API_KEY,
    CONF_NAME,
    ENERGY_WATT_HOUR,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_ENERGY_GENERATION = "energy_generation"
ATTR_POWER_GENERATION = "power_generation"
ATTR_ENERGY_CONSUMPTION = "energy_consumption"
ATTR_POWER_CONSUMPTION = "power_consumption"
ATTR_EFFICIENCY = "efficiency"

CONF_SYSTEM_ID = "system_id"

DEFAULT_NAME = "PVOutput"

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PVOutput sensor."""
    pvoutput = PVOutput(
        api_key=config[CONF_API_KEY],
        system_id=config[CONF_SYSTEM_ID],
    )

    try:
        status = await pvoutput.status()
    except PVOutputError:
        _LOGGER.error("Unable to fetch data from PVOutput")
        return

    async_add_entities([PvoutputSensor(pvoutput, status, config[CONF_NAME])])


class PvoutputSensor(SensorEntity):
    """Representation of a PVOutput sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = ENERGY_WATT_HOUR

    def __init__(self, pvoutput: PVOutput, status: Status, name: str) -> None:
        """Initialize a PVOutput sensor."""
        self._attr_name = name
        self.pvoutput = pvoutput
        self.status = status

    @property
    def native_value(self) -> int | None:
        """Return the state of the device."""
        return self.status.energy_generation

    @property
    def extra_state_attributes(self) -> dict[str, int | float | None]:
        """Return the state attributes of the monitored installation."""
        return {
            ATTR_ENERGY_GENERATION: self.status.energy_generation,
            ATTR_POWER_GENERATION: self.status.power_generation,
            ATTR_ENERGY_CONSUMPTION: self.status.energy_consumption,
            ATTR_POWER_CONSUMPTION: self.status.power_consumption,
            ATTR_EFFICIENCY: self.status.normalized_ouput,
            ATTR_TEMPERATURE: self.status.temperature,
            ATTR_VOLTAGE: self.status.voltage,
        }

    async def async_update(self) -> None:
        """Get the latest data from the PVOutput API and updates the state."""
        self.status = await self.pvoutput.status()
