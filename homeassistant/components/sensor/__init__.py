"""Component to interface with various sensors that can be monitored."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final, cast, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, StateType

_LOGGER: Final = logging.getLogger(__name__)

ATTR_LAST_RESET: Final = "last_reset"
ATTR_STATE_CLASS: Final = "state_class"

DOMAIN: Final = "sensor"

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

SCAN_INTERVAL: Final = timedelta(seconds=30)
DEVICE_CLASSES: Final[list[str]] = [
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_CO,  # ppm (parts per million) Carbon Monoxide gas concentration
    DEVICE_CLASS_CO2,  # ppm (parts per million) Carbon Dioxide gas concentration
    DEVICE_CLASS_CURRENT,  # current (A)
    DEVICE_CLASS_ENERGY,  # energy (kWh, Wh)
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_MONETARY,  # Amount of money (currency)
    DEVICE_CLASS_SIGNAL_STRENGTH,  # signal strength (dB/dBm)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
    DEVICE_CLASS_TIMESTAMP,  # timestamp (ISO8601)
    DEVICE_CLASS_PRESSURE,  # pressure (hPa/mbar)
    DEVICE_CLASS_POWER,  # power (W/kW)
    DEVICE_CLASS_POWER_FACTOR,  # power factor (%)
    DEVICE_CLASS_VOLTAGE,  # voltage (V)
    DEVICE_CLASS_GAS,  # gas (m³ or ft³)
]

DEVICE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

# The state represents a measurement in present time
STATE_CLASS_MEASUREMENT: Final = "measurement"
# The state represents a total amount, e.g. a value of a stock portfolio
STATE_CLASS_TOTAL: Final = "total"
# The state represents a monotonically increasing total, e.g. an amount of consumed gas
STATE_CLASS_TOTAL_INCREASING: Final = "total_increasing"

STATE_CLASSES: Final[list[str]] = [
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
]

STATE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.In(STATE_CLASSES))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component = cast(EntityComponent, hass.data[DOMAIN])
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component = cast(EntityComponent, hass.data[DOMAIN])
    return await component.async_unload_entry(entry)


@dataclass
class SensorEntityDescription(EntityDescription):
    """A class that describes sensor entities."""

    state_class: str | None = None
    last_reset: datetime | None = None
    native_unit_of_measurement: str | None = None


class SensorEntity(Entity):
    """Base class for sensor entities."""

    entity_description: SensorEntityDescription
    _attr_last_reset: datetime | None
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: StateType = None
    _attr_state_class: str | None
    _temperature_conversion_reported = False

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        if hasattr(self, "_attr_state_class"):
            return self._attr_state_class
        if hasattr(self, "entity_description"):
            return self.entity_description.state_class
        return None

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if hasattr(self, "_attr_last_reset"):
            return self._attr_last_reset
        if hasattr(self, "entity_description"):
            return self.entity_description.last_reset
        return None

    @property
    def capability_attributes(self) -> Mapping[str, Any] | None:
        """Return the capability attributes."""
        if state_class := self.state_class:
            return {ATTR_STATE_CLASS: state_class}

        return None

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        if last_reset := self.last_reset:
            return {ATTR_LAST_RESET: last_reset.isoformat()}

        return None

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if hasattr(self, "_attr_native_unit_of_measurement"):
            return self._attr_native_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, after unit conversion."""
        if (
            hasattr(self, "_attr_unit_of_measurement")
            and self._attr_unit_of_measurement is not None
        ):
            return self._attr_unit_of_measurement
        if (
            hasattr(self, "entity_description")
            and self.entity_description.unit_of_measurement is not None
        ):
            return self.entity_description.unit_of_measurement

        native_unit_of_measurement = self.native_unit_of_measurement

        if native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            return self.hass.config.units.temperature_unit

        return native_unit_of_measurement

    @property
    def state(self) -> Any:
        """Return the state of the sensor and perform unit conversions, if needed."""
        # Test if _attr_state has been set in this instance
        if "_attr_state" in self.__dict__:
            return self._attr_state

        unit_of_measurement = self.native_unit_of_measurement
        value = self.native_value

        units = self.hass.config.units
        if (
            value is not None
            and unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT)
            and unit_of_measurement != units.temperature_unit
        ):
            if (
                self.device_class != DEVICE_CLASS_TEMPERATURE
                and not self._temperature_conversion_reported
            ):
                self._temperature_conversion_reported = True
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    "Entity %s (%s) with device_class %s reports a temperature in "
                    "%s which will be converted to %s. Temperature conversion for "
                    "entities without correct device_class is deprecated and will"
                    " be removed from Home Assistant Core 2022.3. Please update "
                    "your configuration if device_class is manually configured, "
                    "otherwise %s",
                    self.entity_id,
                    type(self),
                    self.device_class,
                    unit_of_measurement,
                    units.temperature_unit,
                    report_issue,
                )
            value_s = str(value)
            prec = len(value_s) - value_s.index(".") - 1 if "." in value_s else 0
            # Suppress ValueError (Could not convert sensor_value to float)
            with suppress(ValueError):
                temp = units.temperature(float(value), unit_of_measurement)
                value = str(round(temp) if prec == 0 else round(temp, prec))

        return value

    def __repr__(self) -> str:
        """Return the representation.

        Entity.__repr__ includes the state in the generated string, this fails if we're
        called before self.hass is set.
        """
        if not self.hass:
            return f"<Entity {self.name}>"

        return super().__repr__()
