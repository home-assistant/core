"""SAJ solar inverter interface."""
from __future__ import annotations

from datetime import date
import logging

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
    MASS_KILOGRAMS,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, INVERTER_TYPES
from .coordinator import SAJDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SAJ_UNIT_MAPPINGS = {
    "": None,
    "h": TIME_HOURS,
    "kg": MASS_KILOGRAMS,
    "kWh": ENERGY_KILO_WATT_HOUR,
    "W": POWER_WATT,
    "°C": TEMP_CELSIUS,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=INVERTER_TYPES[0]): vol.In(INVERTER_TYPES),
        vol.Inclusive(CONF_USERNAME, "credentials"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "credentials"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SAJ sensors."""
    inverter: SAJDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await inverter.async_refresh()
    async_add_entities(
        SAJSensor(inverter, sensor) for sensor in inverter.get_enabled_sensors()
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SAJ inverter with yaml."""
    _LOGGER.warning(
        "Loading SAJ Solar inverter integration via yaml is deprecated. "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


class SAJSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SAJ sensor."""

    def __init__(
        self, coordinator: SAJDataUpdateCoordinator, pysaj_sensor: pysaj.Sensor
    ) -> None:
        """Initialize the SAJ sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serialnumber}_{pysaj_sensor.name}"
        self._sensor = pysaj_sensor

        if pysaj_sensor.name in ("current_power", "temperature"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if pysaj_sensor.name == "total_yield":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_info = coordinator.device_info

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.coordinator.name != DEFAULT_NAME:
            return f"{self.coordinator.name} {self._sensor.name}"

        return f"SAJ Inverter {self._sensor.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._sensor.value

    @property
    def available(self) -> bool:
        """
        Return True if device is available.

        Note: SAJ inverters are powered by DC via solar panels and thus are
        offline after the sun has set, but we keep some sensor available.
        """
        if self._sensor.per_total_basis or (
            self._sensor.per_day_basis and date.today() == self._sensor.date
        ):
            # filter out invalid zero value
            return self._sensor.value is not None and self._sensor.value > 0

        return super().available

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SAJ_UNIT_MAPPINGS[self._sensor.unit]

    @property
    def device_class(self):
        """Return the device class the sensor belongs to."""
        if self.native_unit_of_measurement == POWER_WATT:
            return SensorDeviceClass.POWER
        if self.native_unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            return SensorDeviceClass.ENERGY
        if self.native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            return SensorDeviceClass.TEMPERATURE
