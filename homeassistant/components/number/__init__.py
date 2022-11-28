"""Component to allow numeric input for platforms."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import dataclasses
from datetime import timedelta
import inspect
import logging
from math import ceil, floor
from typing import Any, Final, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    CONF_UNIT_OF_MEASUREMENT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import BaseUnitConverter, TemperatureConverter

from .const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DOMAIN,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


class NumberDeviceClass(StrEnum):
    """Device class for numbers."""

    # NumberDeviceClass should be aligned with SensorDeviceClass

    APPARENT_POWER = "apparent_power"
    """Apparent power.

    Unit of measurement: `VA`
    """

    AQI = "aqi"
    """Air Quality Index.

    Unit of measurement: `None`
    """

    BATTERY = "battery"
    """Percentage of battery that is left.

    Unit of measurement: `%`
    """

    CO = "carbon_monoxide"
    """Carbon Monoxide gas concentration.

    Unit of measurement: `ppm` (parts per million)
    """

    CO2 = "carbon_dioxide"
    """Carbon Dioxide gas concentration.

    Unit of measurement: `ppm` (parts per million)
    """

    CURRENT = "current"
    """Current.

    Unit of measurement: `A`
    """

    DISTANCE = "distance"
    """Generic distance.

    Unit of measurement: `LENGTH_*` units
    - SI /metric: `mm`, `cm`, `m`, `km`
    - USCS / imperial: `in`, `ft`, `yd`, `mi`
    """

    ENERGY = "energy"
    """Energy.

    Unit of measurement: `Wh`, `kWh`, `MWh`, `GJ`
    """

    FREQUENCY = "frequency"
    """Frequency.

    Unit of measurement: `Hz`, `kHz`, `MHz`, `GHz`
    """

    GAS = "gas"
    """Gas.

    Unit of measurement: `m³`, `ft³`
    """

    HUMIDITY = "humidity"
    """Relative humidity.

    Unit of measurement: `%`
    """

    ILLUMINANCE = "illuminance"
    """Illuminance.

    Unit of measurement: `lx`, `lm`
    """

    MOISTURE = "moisture"
    """Moisture.

    Unit of measurement: `%`
    """

    MONETARY = "monetary"
    """Amount of money.

    Unit of measurement: ISO4217 currency code

    See https://en.wikipedia.org/wiki/ISO_4217#Active_codes for active codes
    """

    NITROGEN_DIOXIDE = "nitrogen_dioxide"
    """Amount of NO2.

    Unit of measurement: `µg/m³`
    """

    NITROGEN_MONOXIDE = "nitrogen_monoxide"
    """Amount of NO.

    Unit of measurement: `µg/m³`
    """

    NITROUS_OXIDE = "nitrous_oxide"
    """Amount of N2O.

    Unit of measurement: `µg/m³`
    """

    OZONE = "ozone"
    """Amount of O3.

    Unit of measurement: `µg/m³`
    """

    PM1 = "pm1"
    """Particulate matter <= 0.1 μm.

    Unit of measurement: `µg/m³`
    """

    PM10 = "pm10"
    """Particulate matter <= 10 μm.

    Unit of measurement: `µg/m³`
    """

    PM25 = "pm25"
    """Particulate matter <= 2.5 μm.

    Unit of measurement: `µg/m³`
    """

    POWER_FACTOR = "power_factor"
    """Power factor.

    Unit of measurement: `%`
    """

    POWER = "power"
    """Power.

    Unit of measurement: `W`, `kW`
    """

    PRECIPITATION = "precipitation"
    """Precipitation.

    Unit of measurement:
    - SI / metric: `mm`
    - USCS / imperial: `in`
    """

    PRECIPITATION_INTENSITY = "precipitation_intensity"
    """Precipitation intensity.

    Unit of measurement: UnitOfVolumetricFlux
    - SI /metric: `mm/d`, `mm/h`
    - USCS / imperial: `in/d`, `in/h`
    """

    PRESSURE = "pressure"
    """Pressure.

    Unit of measurement:
    - `mbar`, `cbar`, `bar`
    - `Pa`, `hPa`, `kPa`
    - `inHg`
    - `psi`
    """

    REACTIVE_POWER = "reactive_power"
    """Reactive power.

    Unit of measurement: `var`
    """

    SIGNAL_STRENGTH = "signal_strength"
    """Signal strength.

    Unit of measurement: `dB`, `dBm`
    """

    SPEED = "speed"
    """Generic speed.

    Unit of measurement: `SPEED_*` units or `UnitOfVolumetricFlux`
    - SI /metric: `mm/d`, `mm/h`, `m/s`, `km/h`
    - USCS / imperial: `in/d`, `in/h`, `ft/s`, `mph`
    - Nautical: `kn`
    """

    SULPHUR_DIOXIDE = "sulphur_dioxide"
    """Amount of SO2.

    Unit of measurement: `µg/m³`
    """

    TEMPERATURE = "temperature"
    """Temperature.

    Unit of measurement: `°C`, `°F`
    """

    VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
    """Amount of VOC.

    Unit of measurement: `µg/m³`
    """

    VOLTAGE = "voltage"
    """Voltage.

    Unit of measurement: `V`
    """

    VOLUME = "volume"
    """Generic volume.

    Unit of measurement: `VOLUME_*` units
    - SI / metric: `mL`, `L`, `m³`
    - USCS / imperial: `fl. oz.`, `ft³`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    WATER = "water"
    """Water.

    Unit of measurement:
    - SI / metric: `m³`, `L`
    - USCS / imperial: `ft³`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    WEIGHT = "weight"
    """Generic weight, represents a measurement of an object's mass.

    Weight is used instead of mass to fit with every day language.

    Unit of measurement: `MASS_*` units
    - SI / metric: `µg`, `mg`, `g`, `kg`
    - USCS / imperial: `oz`, `lb`
    """

    WIND_SPEED = "wind_speed"
    """Wind speed.

    Unit of measurement: `SPEED_*` units
    - SI /metric: `m/s`, `km/h`
    - USCS / imperial: `ft/s`, `mph`
    - Nautical: `kn`
    """


DEVICE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(NumberDeviceClass))


class NumberMode(StrEnum):
    """Modes for number entities."""

    AUTO = "auto"
    BOX = "box"
    SLIDER = "slider"


UNIT_CONVERTERS: dict[str, type[BaseUnitConverter]] = {
    NumberDeviceClass.TEMPERATURE: TemperatureConverter,
}

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Number entities."""
    component = hass.data[DOMAIN] = EntityComponent[NumberEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.Coerce(float)},
        async_set_value,
    )

    return True


async def async_set_value(entity: NumberEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data["value"]
    if value < entity.min_value or value > entity.max_value:
        raise ValueError(
            f"Value {value} for {entity.name} is outside valid range {entity.min_value} - {entity.max_value}"
        )
    try:
        native_value = entity.convert_to_native_value(value)
        # Clamp to the native range
        native_value = min(
            max(native_value, entity.native_min_value), entity.native_max_value
        )
        await entity.async_set_native_value(native_value)
    except NotImplementedError:
        await entity.async_set_value(value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[NumberEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[NumberEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclasses.dataclass
class NumberEntityDescription(EntityDescription):
    """A class that describes number entities."""

    max_value: None = None
    min_value: None = None
    native_max_value: float | None = None
    native_min_value: float | None = None
    native_unit_of_measurement: str | None = None
    native_step: float | None = None
    step: None = None
    unit_of_measurement: None = None  # Type override, use native_unit_of_measurement

    def __post_init__(self) -> None:
        """Post initialisation processing."""
        if (
            self.max_value is not None
            or self.min_value is not None
            or self.step is not None
            or self.unit_of_measurement is not None
        ):
            if self.__class__.__name__ == "NumberEntityDescription":  # type: ignore[unreachable]
                caller = inspect.stack()[2]
                module = inspect.getmodule(caller[0])
            else:
                module = inspect.getmodule(self)
            if module and module.__file__ and "custom_components" in module.__file__:
                report_issue = "report it to the custom integration author."
            else:
                report_issue = (
                    "create a bug report at "
                    "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
                )
            _LOGGER.warning(
                "%s is setting deprecated attributes on an instance of "
                "NumberEntityDescription, this is not valid and will be unsupported "
                "from Home Assistant 2022.10. Please %s",
                module.__name__ if module else self.__class__.__name__,
                report_issue,
            )
            self.native_unit_of_measurement = self.unit_of_measurement


def ceil_decimal(value: float, precision: float = 0) -> float:
    """Return the ceiling of f with d decimals.

    This is a simple implementation which ignores floating point inexactness.
    """
    factor = 10**precision
    return ceil(value * factor) / factor


def floor_decimal(value: float, precision: float = 0) -> float:
    """Return the floor of f with d decimals.

    This is a simple implementation which ignores floating point inexactness.
    """
    factor = 10**precision
    return floor(value * factor) / factor


class NumberEntity(Entity):
    """Representation of a Number entity."""

    entity_description: NumberEntityDescription
    _attr_max_value: None
    _attr_min_value: None
    _attr_mode: NumberMode = NumberMode.AUTO
    _attr_state: None = None
    _attr_step: None
    _attr_unit_of_measurement: None  # Subclasses of NumberEntity should not set this
    _attr_value: None
    _attr_native_max_value: float
    _attr_native_min_value: float
    _attr_native_step: float
    _attr_native_value: float | None = None
    _attr_native_unit_of_measurement: str | None
    _deprecated_number_entity_reported = False
    _number_option_unit_of_measurement: str | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        if any(
            method in cls.__dict__
            for method in (
                "async_set_value",
                "max_value",
                "min_value",
                "set_value",
                "step",
                "unit_of_measurement",
                "value",
            )
        ):
            module = inspect.getmodule(cls)
            if module and module.__file__ and "custom_components" in module.__file__:
                report_issue = "report it to the custom integration author."
            else:
                report_issue = (
                    "create a bug report at "
                    "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
                )
            _LOGGER.warning(
                "%s::%s is overriding deprecated methods on an instance of "
                "NumberEntity, this is not valid and will be unsupported "
                "from Home Assistant 2022.10. Please %s",
                cls.__module__,
                cls.__name__,
                report_issue,
            )

    async def async_internal_added_to_hass(self) -> None:
        """Call when the number entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self.async_registry_entry_updated()

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_MIN: self.min_value,
            ATTR_MAX: self.max_value,
            ATTR_STEP: self.step,
            ATTR_MODE: self.mode,
        }

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if hasattr(self, "_attr_native_min_value"):
            return self._attr_native_min_value
        if (
            hasattr(self, "entity_description")
            and self.entity_description.native_min_value is not None
        ):
            return self.entity_description.native_min_value
        return DEFAULT_MIN_VALUE

    @property
    @final
    def min_value(self) -> float:
        """Return the minimum value."""
        if hasattr(self, "_attr_min_value"):
            self._report_deprecated_number_entity()
            return self._attr_min_value  # type: ignore[return-value]
        if (
            hasattr(self, "entity_description")
            and self.entity_description.min_value is not None
        ):
            self._report_deprecated_number_entity()  # type: ignore[unreachable]
            return self.entity_description.min_value
        return self._convert_to_state_value(self.native_min_value, floor_decimal)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if hasattr(self, "_attr_native_max_value"):
            return self._attr_native_max_value
        if (
            hasattr(self, "entity_description")
            and self.entity_description.native_max_value is not None
        ):
            return self.entity_description.native_max_value
        return DEFAULT_MAX_VALUE

    @property
    @final
    def max_value(self) -> float:
        """Return the maximum value."""
        if hasattr(self, "_attr_max_value"):
            self._report_deprecated_number_entity()
            return self._attr_max_value  # type: ignore[return-value]
        if (
            hasattr(self, "entity_description")
            and self.entity_description.max_value is not None
        ):
            self._report_deprecated_number_entity()  # type: ignore[unreachable]
            return self.entity_description.max_value
        return self._convert_to_state_value(self.native_max_value, ceil_decimal)

    @property
    def native_step(self) -> float | None:
        """Return the increment/decrement step."""
        if (
            hasattr(self, "entity_description")
            and self.entity_description.native_step is not None
        ):
            return self.entity_description.native_step
        return None

    @property
    @final
    def step(self) -> float:
        """Return the increment/decrement step."""
        if hasattr(self, "_attr_step"):
            self._report_deprecated_number_entity()
            return self._attr_step  # type: ignore[return-value]
        if (
            hasattr(self, "entity_description")
            and self.entity_description.step is not None
        ):
            self._report_deprecated_number_entity()  # type: ignore[unreachable]
            return self.entity_description.step
        if hasattr(self, "_attr_native_step"):
            return self._attr_native_step
        if (native_step := self.native_step) is not None:
            return native_step
        step = DEFAULT_STEP
        value_range = abs(self.max_value - self.min_value)
        if value_range != 0:
            while value_range <= step:
                step /= 10.0
        return step

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the entity."""
        return self._attr_mode

    @property
    @final
    def state(self) -> float | None:
        """Return the entity state."""
        return self.value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, if any."""
        if hasattr(self, "_attr_native_unit_of_measurement"):
            return self._attr_native_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    @property
    @final
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, after unit conversion."""
        if self._number_option_unit_of_measurement:
            return self._number_option_unit_of_measurement

        if hasattr(self, "_attr_unit_of_measurement"):
            self._report_deprecated_number_entity()
            return self._attr_unit_of_measurement
        if (
            hasattr(self, "entity_description")
            and self.entity_description.unit_of_measurement is not None
        ):
            return self.entity_description.unit_of_measurement  # type: ignore[unreachable]

        native_unit_of_measurement = self.native_unit_of_measurement

        if (
            self.device_class == NumberDeviceClass.TEMPERATURE
            and native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT)
        ):
            return self.hass.config.units.temperature_unit

        return native_unit_of_measurement

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._attr_native_value

    @property
    @final
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if hasattr(self, "_attr_value"):
            self._report_deprecated_number_entity()
            return self._attr_value

        if (native_value := self.native_value) is None:
            return native_value
        return self._convert_to_state_value(native_value, round)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_native_value, value)

    @final
    def set_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError()

    @final
    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_value, value)

    def _convert_to_state_value(
        self, value: float, method: Callable[[float, int], float]
    ) -> float:
        """Convert a value in the number's native unit to the configured unit."""

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        device_class = self.device_class

        if (
            native_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERTERS
        ):
            assert native_unit_of_measurement
            assert unit_of_measurement

            value_s = str(value)
            prec = len(value_s) - value_s.index(".") - 1 if "." in value_s else 0

            # Suppress ValueError (Could not convert value to float)
            with suppress(ValueError):
                value_new: float = UNIT_CONVERTERS[device_class].convert(
                    value,
                    native_unit_of_measurement,
                    unit_of_measurement,
                )

                # Round to the wanted precision
                value = method(value_new, prec)

        return value

    def convert_to_native_value(self, value: float) -> float:
        """Convert a value to the number's native unit."""

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        device_class = self.device_class

        if (
            value is not None
            and native_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERTERS
        ):
            assert native_unit_of_measurement
            assert unit_of_measurement

            value = UNIT_CONVERTERS[device_class].convert(
                value,
                unit_of_measurement,
                native_unit_of_measurement,
            )

        return value

    def _report_deprecated_number_entity(self) -> None:
        """Report that the number entity has not been upgraded."""
        if not self._deprecated_number_entity_reported:
            self._deprecated_number_entity_reported = True
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                "Entity %s (%s) is using deprecated NumberEntity features which will "
                "be unsupported from Home Assistant Core 2022.10, please %s",
                self.entity_id,
                type(self),
                report_issue,
            )

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        assert self.registry_entry
        if (
            (number_options := self.registry_entry.options.get(DOMAIN))
            and (custom_unit := number_options.get(CONF_UNIT_OF_MEASUREMENT))
            and (device_class := self.device_class) in UNIT_CONVERTERS
            and self.native_unit_of_measurement
            in UNIT_CONVERTERS[device_class].VALID_UNITS
            and custom_unit in UNIT_CONVERTERS[device_class].VALID_UNITS
        ):
            self._number_option_unit_of_measurement = custom_unit
            return

        self._number_option_unit_of_measurement = None


@dataclasses.dataclass
class NumberExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    native_max_value: float | None
    native_min_value: float | None
    native_step: float | None
    native_unit_of_measurement: str | None
    native_value: float | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the number data."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> NumberExtraStoredData | None:
        """Initialize a stored number state from a dict."""
        try:
            return cls(
                restored["native_max_value"],
                restored["native_min_value"],
                restored["native_step"],
                restored["native_unit_of_measurement"],
                restored["native_value"],
            )
        except KeyError:
            return None


class RestoreNumber(NumberEntity, RestoreEntity):
    """Mixin class for restoring previous number state."""

    @property
    def extra_restore_state_data(self) -> NumberExtraStoredData:
        """Return number specific state data to be restored."""
        return NumberExtraStoredData(
            self.native_max_value,
            self.native_min_value,
            self.native_step,
            self.native_unit_of_measurement,
            self.native_value,
        )

    async def async_get_last_number_data(self) -> NumberExtraStoredData | None:
        """Restore native_*."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return NumberExtraStoredData.from_dict(restored_last_extra_data.as_dict())
