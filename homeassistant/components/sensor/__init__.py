"""Component to interface with various sensors that can be monitored."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import inspect
import logging
from typing import Any, Final, cast, final

import ciso8601
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_DATE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_FREQUENCY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_NITROGEN_DIOXIDE,
    DEVICE_CLASS_NITROGEN_MONOXIDE,
    DEVICE_CLASS_NITROUS_OXIDE,
    DEVICE_CLASS_OZONE,
    DEVICE_CLASS_PM1,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_SULPHUR_DIOXIDE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
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

from .const import CONF_STATE_CLASS  # noqa: F401

_LOGGER: Final = logging.getLogger(__name__)

ATTR_LAST_RESET: Final = "last_reset"  # Deprecated, to be removed in 2021.11
ATTR_STATE_CLASS: Final = "state_class"

DOMAIN: Final = "sensor"

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

SCAN_INTERVAL: Final = timedelta(seconds=30)
DEVICE_CLASSES: Final[list[str]] = [
    DEVICE_CLASS_AQI,  # Air Quality Index
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_CO,  # ppm (parts per million) Carbon Monoxide gas concentration
    DEVICE_CLASS_CO2,  # ppm (parts per million) Carbon Dioxide gas concentration
    DEVICE_CLASS_CURRENT,  # current (A)
    DEVICE_CLASS_DATE,  # date (ISO8601)
    DEVICE_CLASS_ENERGY,  # energy (kWh, Wh)
    DEVICE_CLASS_FREQUENCY,  # frequency (Hz, kHz, MHz, GHz)
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_MONETARY,  # Amount of money (currency)
    DEVICE_CLASS_OZONE,  # Amount of O3 (µg/m³)
    DEVICE_CLASS_NITROGEN_DIOXIDE,  # Amount of NO2 (µg/m³)
    DEVICE_CLASS_NITROUS_OXIDE,  # Amount of N2O  (µg/m³)
    DEVICE_CLASS_NITROGEN_MONOXIDE,  # Amount of NO (µg/m³)
    DEVICE_CLASS_PM1,  # Particulate matter <= 0.1 μm (µg/m³)
    DEVICE_CLASS_PM10,  # Particulate matter <= 10 μm (µg/m³)
    DEVICE_CLASS_PM25,  # Particulate matter <= 2.5 μm (µg/m³)
    DEVICE_CLASS_SIGNAL_STRENGTH,  # signal strength (dB/dBm)
    DEVICE_CLASS_SULPHUR_DIOXIDE,  # Amount of SO2 (µg/m³)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
    DEVICE_CLASS_TIMESTAMP,  # timestamp (ISO8601)
    DEVICE_CLASS_PRESSURE,  # pressure (hPa/mbar)
    DEVICE_CLASS_POWER,  # power (W/kW)
    DEVICE_CLASS_POWER_FACTOR,  # power factor (%)
    DEVICE_CLASS_VOLTAGE,  # voltage (V)
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,  # Amount of VOC (µg/m³)
    DEVICE_CLASS_GAS,  # gas (m³ or ft³)
]

DEVICE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

# The state represents a measurement in present time
STATE_CLASS_MEASUREMENT: Final = "measurement"
# The state represents a total amount, e.g. net energy consumption
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

    last_reset: datetime | None = None  # Deprecated, to be removed in 2021.11
    native_unit_of_measurement: str | None = None
    state_class: str | None = None
    unit_of_measurement: None = None  # Type override, use native_unit_of_measurement

    def __post_init__(self) -> None:
        """Post initialisation processing."""
        if self.unit_of_measurement:
            caller = inspect.stack()[2]  # type: ignore[unreachable]
            module = inspect.getmodule(caller[0])
            if "custom_components" in module.__file__:
                report_issue = "report it to the custom component author."
            else:
                report_issue = (
                    "create a bug report at "
                    "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
                )
            _LOGGER.warning(
                "%s is setting 'unit_of_measurement' on an instance of "
                "SensorEntityDescription, this is not valid and will be unsupported "
                "from Home Assistant 2021.11. Please %s",
                module.__name__,
                report_issue,
            )
            self.native_unit_of_measurement = self.unit_of_measurement


class SensorEntity(Entity):
    """Base class for sensor entities."""

    entity_description: SensorEntityDescription
    _attr_last_reset: datetime | None  # Deprecated, to be removed in 2021.11
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: StateType | date | datetime = None
    _attr_state_class: str | None
    _attr_state: None = None  # Subclasses of SensorEntity should not set this
    _attr_unit_of_measurement: None = (
        None  # Subclasses of SensorEntity should not set this
    )
    _last_reset_reported = False
    _temperature_conversion_reported = False

    # Temporary private attribute to track if deprecation has been logged.
    __datetime_as_string_deprecation_logged = False

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        if hasattr(self, "_attr_state_class"):
            return self._attr_state_class
        if hasattr(self, "entity_description"):
            return self.entity_description.state_class
        return None

    @property
    def last_reset(self) -> datetime | None:  # Deprecated, to be removed in 2021.11
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
            if (
                self.state_class == STATE_CLASS_MEASUREMENT
                and not self._last_reset_reported
            ):
                self._last_reset_reported = True
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    "Entity %s (%s) with state_class %s has set last_reset. Setting "
                    "last_reset for entities with state_class other than 'total' is "
                    "deprecated and will be removed from Home Assistant Core 2021.11. "
                    "Please update your configuration if state_class is manually "
                    "configured, otherwise %s",
                    self.entity_id,
                    type(self),
                    self.state_class,
                    report_issue,
                )

            return {ATTR_LAST_RESET: last_reset.isoformat()}

        return None

    @property
    def native_value(self) -> StateType | date | datetime:
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

    @final
    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, after unit conversion."""
        # Support for _attr_unit_of_measurement will be removed in Home Assistant 2021.11
        if (
            hasattr(self, "_attr_unit_of_measurement")
            and self._attr_unit_of_measurement is not None
        ):
            return self._attr_unit_of_measurement  # type: ignore

        native_unit_of_measurement = self.native_unit_of_measurement

        if native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            return self.hass.config.units.temperature_unit

        return native_unit_of_measurement

    @final
    @property
    def state(self) -> Any:
        """Return the state of the sensor and perform unit conversions, if needed."""
        unit_of_measurement = self.native_unit_of_measurement
        value = self.native_value
        device_class = self.device_class

        # We have an old non-datetime value, warn about it and convert it during
        # the deprecation period.
        if (
            value is not None
            and device_class in (DEVICE_CLASS_DATE, DEVICE_CLASS_TIMESTAMP)
            and not isinstance(value, (date, datetime))
        ):
            # Deprecation warning for date/timestamp device classes
            if not self.__datetime_as_string_deprecation_logged:
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    "%s is providing a string for its state, while the device "
                    "class is '%s', this is not valid and will be unsupported "
                    "from Home Assistant 2022.2. Please %s",
                    self.entity_id,
                    device_class,
                    report_issue,
                )
                self.__datetime_as_string_deprecation_logged = True

            # Anyways, lets validate the date at least..
            try:
                value = ciso8601.parse_datetime(str(value))
            except (ValueError, IndexError) as error:
                raise ValueError(
                    f"Invalid date/datetime: {self.entity_id} provide state '{value}', "
                    f"while it has device class '{device_class}'"
                ) from error

            if value.tzinfo is not None and value.tzinfo != timezone.utc:
                value = value.astimezone(timezone.utc)

            # Convert the date object to a standardized state string.
            if device_class == DEVICE_CLASS_DATE:
                return value.date().isoformat()

            return value.isoformat(timespec="seconds")

        # Received a datetime
        if value is not None and device_class == DEVICE_CLASS_TIMESTAMP:
            try:
                # We cast the value, to avoid using isinstance, but satisfy
                # typechecking. The errors are guarded in this try.
                value = cast(datetime, value)
                if value.tzinfo is None:
                    raise ValueError(
                        f"Invalid datetime: {self.entity_id} provides state '{value}', "
                        "which is missing timezone information"
                    )

                if value.tzinfo != timezone.utc:
                    value = value.astimezone(timezone.utc)

                return value.isoformat(timespec="seconds")
            except (AttributeError, TypeError) as err:
                raise ValueError(
                    f"Invalid datetime: {self.entity_id} has a timestamp device class"
                    f"but does not provide a datetime state but {type(value)}"
                ) from err

        # Received a date value
        if value is not None and device_class == DEVICE_CLASS_DATE:
            try:
                return value.isoformat()  # type: ignore
            except (AttributeError, TypeError) as err:
                raise ValueError(
                    f"Invalid date: {self.entity_id} has a date device class"
                    f"but does not provide a date state but {type(value)}"
                ) from err

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
                temp = units.temperature(float(value), unit_of_measurement)  # type: ignore
                value = round(temp) if prec == 0 else round(temp, prec)

        return value

    def __repr__(self) -> str:
        """Return the representation.

        Entity.__repr__ includes the state in the generated string, this fails if we're
        called before self.hass is set.
        """
        if not self.hass:
            return f"<Entity {self.name}>"

        return super().__repr__()
