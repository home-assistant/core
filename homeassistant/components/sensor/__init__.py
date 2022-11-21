"""Component to interface with various sensors that can be monitored."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
import logging
from math import floor, log10
from typing import Any, Final, cast, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401, pylint: disable=[hass-deprecated-import]
    CONF_UNIT_OF_MEASUREMENT,
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
    TEMP_KELVIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    DistanceConverter,
    MassConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    VolumeConverter,
)

from .const import CONF_STATE_CLASS  # noqa: F401

_LOGGER: Final = logging.getLogger(__name__)

ATTR_LAST_RESET: Final = "last_reset"
ATTR_STATE_CLASS: Final = "state_class"

DOMAIN: Final = "sensor"

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

SCAN_INTERVAL: Final = timedelta(seconds=30)


class SensorDeviceClass(StrEnum):
    """Device class for sensors."""

    # Non-numerical device classes
    DATE = "date"
    """Date.

    Unit of measurement: `None`

    ISO8601 format: https://en.wikipedia.org/wiki/ISO_8601
    """

    DURATION = "duration"
    """Fixed duration.

    Unit of measurement: `d`, `h`, `min`, `s`
    """

    TIMESTAMP = "timestamp"
    """Timestamp.

    Unit of measurement: `None`

    ISO8601 format: https://en.wikipedia.org/wiki/ISO_8601
    """

    # Numerical device classes, these should be aligned with NumberDeviceClass
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


DEVICE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(SensorDeviceClass))

# DEVICE_CLASSES is deprecated as of 2021.12
# use the SensorDeviceClass enum instead.
DEVICE_CLASSES: Final[list[str]] = [cls.value for cls in SensorDeviceClass]


class SensorStateClass(StrEnum):
    """State class for sensors."""

    MEASUREMENT = "measurement"
    """The state represents a measurement in present time."""

    TOTAL = "total"
    """The state represents a total amount.

    For example: net energy consumption"""

    TOTAL_INCREASING = "total_increasing"
    """The state represents a monotonically increasing total.

    For example: an amount of consumed gas"""


STATE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(SensorStateClass))


# STATE_CLASS* is deprecated as of 2021.12
# use the SensorStateClass enum instead.
STATE_CLASS_MEASUREMENT: Final = "measurement"
STATE_CLASS_TOTAL: Final = "total"
STATE_CLASS_TOTAL_INCREASING: Final = "total_increasing"
STATE_CLASSES: Final[list[str]] = [cls.value for cls in SensorStateClass]

# Note: this needs to be aligned with frontend: OVERRIDE_SENSOR_UNITS in
# `entity-registry-settings.ts`
UNIT_CONVERTERS: dict[SensorDeviceClass | str | None, type[BaseUnitConverter]] = {
    SensorDeviceClass.DISTANCE: DistanceConverter,
    SensorDeviceClass.GAS: VolumeConverter,
    SensorDeviceClass.PRECIPITATION: DistanceConverter,
    SensorDeviceClass.PRESSURE: PressureConverter,
    SensorDeviceClass.SPEED: SpeedConverter,
    SensorDeviceClass.TEMPERATURE: TemperatureConverter,
    SensorDeviceClass.VOLUME: VolumeConverter,
    SensorDeviceClass.WATER: VolumeConverter,
    SensorDeviceClass.WEIGHT: MassConverter,
    SensorDeviceClass.WIND_SPEED: SpeedConverter,
}

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent[SensorEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[SensorEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[SensorEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class SensorEntityDescription(EntityDescription):
    """A class that describes sensor entities."""

    device_class: SensorDeviceClass | str | None = None
    suggested_unit_of_measurement: str | None = None
    last_reset: datetime | None = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | str | None = None
    unit_of_measurement: None = None  # Type override, use native_unit_of_measurement


class SensorEntity(Entity):
    """Base class for sensor entities."""

    entity_description: SensorEntityDescription
    _attr_device_class: SensorDeviceClass | str | None
    _attr_last_reset: datetime | None
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: StateType | date | datetime | Decimal = None
    _attr_state_class: SensorStateClass | str | None
    _attr_state: None = None  # Subclasses of SensorEntity should not set this
    _attr_suggested_unit_of_measurement: str | None
    _attr_unit_of_measurement: None = (
        None  # Subclasses of SensorEntity should not set this
    )
    _last_reset_reported = False
    _sensor_option_unit_of_measurement: str | None = None

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)

        if self.unique_id is None:
            return
        registry = er.async_get(self.hass)
        if not (
            entity_id := registry.async_get_entity_id(
                platform.domain, platform.platform_name, self.unique_id
            )
        ):
            return
        registry_entry = registry.async_get(entity_id)
        assert registry_entry

        # Store unit override according to automatic unit conversion rules if:
        # - no unit override is stored in the entity registry
        # - units have changed
        # - the unit stored in the registry matches automatic unit conversion rules
        # This allows integrations to drop custom unit conversion and rely on automatic
        # conversion.
        registry_unit = registry_entry.unit_of_measurement
        if (
            DOMAIN not in registry_entry.options
            and f"{DOMAIN}.private" not in registry_entry.options
            and self.unit_of_measurement != registry_unit
            and (suggested_unit := self._get_initial_suggested_unit()) == registry_unit
        ):
            registry.async_update_entity_options(
                entity_id,
                f"{DOMAIN}.private",
                {"suggested_unit_of_measurement": suggested_unit},
            )

    async def async_internal_added_to_hass(self) -> None:
        """Call when the sensor entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self.async_registry_entry_updated()

    @property
    def device_class(self) -> SensorDeviceClass | str | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    def state_class(self) -> SensorStateClass | str | None:
        """Return the state class of this entity, if any."""
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

    def _get_initial_suggested_unit(self) -> str | None:
        """Return initial suggested unit of measurement."""
        # Unit suggested by the integration
        suggested_unit_of_measurement = self.suggested_unit_of_measurement

        if suggested_unit_of_measurement is None:
            # Fallback to suggested by the unit conversion rules
            suggested_unit_of_measurement = self.hass.config.units.get_converted_unit(
                self.device_class, self.native_unit_of_measurement
            )

        return suggested_unit_of_measurement

    def get_initial_entity_options(self) -> er.EntityOptionsType | None:
        """Return initial entity options.

        These will be stored in the entity registry the first time the entity is seen,
        and then never updated.
        """
        suggested_unit_of_measurement = self._get_initial_suggested_unit()
        if suggested_unit_of_measurement is None:
            return None

        return {
            f"{DOMAIN}.private": {
                "suggested_unit_of_measurement": suggested_unit_of_measurement
            }
        }

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        if last_reset := self.last_reset:
            if (
                self.state_class != SensorStateClass.TOTAL
                and not self._last_reset_reported
            ):
                self._last_reset_reported = True
                report_issue = self._suggest_report_issue()
                # This should raise in Home Assistant Core 2022.5
                _LOGGER.warning(
                    "Entity %s (%s) with state_class %s has set last_reset. Setting "
                    "last_reset for entities with state_class other than 'total' is "
                    "not supported. "
                    "Please update your configuration if state_class is manually "
                    "configured, otherwise %s",
                    self.entity_id,
                    type(self),
                    self.state_class,
                    report_issue,
                )

            if self.state_class == SensorStateClass.TOTAL:
                return {ATTR_LAST_RESET: last_reset.isoformat()}

        return None

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
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
    def suggested_unit_of_measurement(self) -> str | None:
        """Return the unit which should be used for the sensor's state.

        This can be used by integrations to override automatic unit conversion rules,
        for example to make a temperature sensor display in °C even if the configured
        unit system prefers °F.

        For sensors without a `unique_id`, this takes precedence over legacy
        temperature conversion rules only.

        For sensors with a `unique_id`, this is applied only if the unit is not set by the user,
        and takes precedence over automatic device-class conversion rules.

        Note:
            suggested_unit_of_measurement is stored in the entity registry the first time
            the entity is seen, and then never updated.
        """
        if hasattr(self, "_attr_suggested_unit_of_measurement"):
            return self._attr_suggested_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.suggested_unit_of_measurement
        return None

    @final
    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, after unit conversion."""
        # Highest priority, for registered entities: unit set by user, with fallback to unit suggested
        # by integration or secondary fallback to unit conversion rules
        if self._sensor_option_unit_of_measurement:
            return self._sensor_option_unit_of_measurement

        # Second priority, for non registered entities: unit suggested by integration
        if not self.registry_entry and self.suggested_unit_of_measurement:
            return self.suggested_unit_of_measurement

        # Third priority: Legacy temperature conversion, which applies
        # to both registered and non registered entities
        native_unit_of_measurement = self.native_unit_of_measurement

        if (
            self.device_class == DEVICE_CLASS_TEMPERATURE
            and native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT)
        ):
            return self.hass.config.units.temperature_unit

        # Fourth priority: Native unit
        return native_unit_of_measurement

    @final
    @property
    def state(self) -> Any:
        """Return the state of the sensor and perform unit conversions, if needed."""
        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        value = self.native_value
        device_class = self.device_class

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
            except (AttributeError, OverflowError, TypeError) as err:
                raise ValueError(
                    f"Invalid datetime: {self.entity_id} has timestamp device class "
                    f"but provides state {value}:{type(value)} resulting in '{err}'"
                ) from err

        # Received a date value
        if value is not None and device_class == DEVICE_CLASS_DATE:
            try:
                # We cast the value, to avoid using isinstance, but satisfy
                # typechecking. The errors are guarded in this try.
                value = cast(date, value)
                return value.isoformat()
            except (AttributeError, TypeError) as err:
                raise ValueError(
                    f"Invalid date: {self.entity_id} has date device class "
                    f"but provides state {value}:{type(value)} resulting in '{err}'"
                ) from err

        if (
            value is not None
            and native_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERTERS
        ):
            assert unit_of_measurement
            assert native_unit_of_measurement
            converter = UNIT_CONVERTERS[device_class]

            value_s = str(value)
            prec = len(value_s) - value_s.index(".") - 1 if "." in value_s else 0

            # Scale the precision when converting to a larger unit
            # For example 1.1 Wh should be rendered as 0.0011 kWh, not 0.0 kWh
            ratio_log = max(
                0,
                log10(
                    converter.get_unit_ratio(
                        native_unit_of_measurement, unit_of_measurement
                    )
                ),
            )
            prec = prec + floor(ratio_log)

            # Suppress ValueError (Could not convert sensor_value to float)
            with suppress(ValueError):
                value_f = float(value)  # type: ignore[arg-type]
                value_f_new = converter.convert(
                    value_f,
                    native_unit_of_measurement,
                    unit_of_measurement,
                )

                # Round to the wanted precision
                value = round(value_f_new) if prec == 0 else round(value_f_new, prec)

        return value

    def __repr__(self) -> str:
        """Return the representation.

        Entity.__repr__ includes the state in the generated string, this fails if we're
        called before self.hass is set.
        """
        if not self.hass:
            return f"<Entity {self.name}>"

        return super().__repr__()

    def _custom_unit_or_none(self, primary_key: str, secondary_key: str) -> str | None:
        """Return a custom unit, or None if it's not compatible with the native unit."""
        assert self.registry_entry
        if (
            (sensor_options := self.registry_entry.options.get(primary_key))
            and (custom_unit := sensor_options.get(secondary_key))
            and (device_class := self.device_class) in UNIT_CONVERTERS
            and self.native_unit_of_measurement
            in UNIT_CONVERTERS[device_class].VALID_UNITS
            and custom_unit in UNIT_CONVERTERS[device_class].VALID_UNITS
        ):
            return cast(str, custom_unit)
        return None

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._sensor_option_unit_of_measurement = self._custom_unit_or_none(
            DOMAIN, CONF_UNIT_OF_MEASUREMENT
        )
        if not self._sensor_option_unit_of_measurement:
            self._sensor_option_unit_of_measurement = self._custom_unit_or_none(
                f"{DOMAIN}.private", "suggested_unit_of_measurement"
            )


@dataclass
class SensorExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    native_value: StateType | date | datetime | Decimal
    native_unit_of_measurement: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""
        native_value: StateType | date | datetime | Decimal | dict[
            str, str
        ] = self.native_value
        if isinstance(native_value, (date, datetime)):
            native_value = {
                "__type": str(type(native_value)),
                "isoformat": native_value.isoformat(),
            }
        if isinstance(native_value, Decimal):
            native_value = {
                "__type": str(type(native_value)),
                "decimal_str": str(native_value),
            }
        return {
            "native_value": native_value,
            "native_unit_of_measurement": self.native_unit_of_measurement,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> SensorExtraStoredData | None:
        """Initialize a stored sensor state from a dict."""
        try:
            native_value = restored["native_value"]
            native_unit_of_measurement = restored["native_unit_of_measurement"]
        except KeyError:
            return None
        try:
            type_ = native_value["__type"]
            if type_ == "<class 'datetime.datetime'>":
                native_value = dt_util.parse_datetime(native_value["isoformat"])
            elif type_ == "<class 'datetime.date'>":
                native_value = dt_util.parse_date(native_value["isoformat"])
            elif type_ == "<class 'decimal.Decimal'>":
                native_value = Decimal(native_value["decimal_str"])
        except TypeError:
            # native_value is not a dict
            pass
        except KeyError:
            # native_value is a dict, but does not have all values
            return None
        except DecimalInvalidOperation:
            # native_value coulnd't be returned from decimal_str
            return None

        return cls(native_value, native_unit_of_measurement)


class RestoreSensor(SensorEntity, RestoreEntity):
    """Mixin class for restoring previous sensor state."""

    @property
    def extra_restore_state_data(self) -> SensorExtraStoredData:
        """Return sensor specific state data to be restored."""
        return SensorExtraStoredData(self.native_value, self.native_unit_of_measurement)

    async def async_get_last_sensor_data(self) -> SensorExtraStoredData | None:
        """Restore native_value and native_unit_of_measurement."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return SensorExtraStoredData.from_dict(restored_last_extra_data.as_dict())
