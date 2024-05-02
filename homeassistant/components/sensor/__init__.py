"""Component to interface with various sensors that can be monitored."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from functools import cached_property, partial
import logging
from math import ceil, floor, isfinite, log10
from typing import Any, Final, Self, cast, final, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
    _DEPRECATED_DEVICE_CLASS_AQI,
    _DEPRECATED_DEVICE_CLASS_BATTERY,
    _DEPRECATED_DEVICE_CLASS_CO,
    _DEPRECATED_DEVICE_CLASS_CO2,
    _DEPRECATED_DEVICE_CLASS_CURRENT,
    _DEPRECATED_DEVICE_CLASS_DATE,
    _DEPRECATED_DEVICE_CLASS_ENERGY,
    _DEPRECATED_DEVICE_CLASS_FREQUENCY,
    _DEPRECATED_DEVICE_CLASS_GAS,
    _DEPRECATED_DEVICE_CLASS_HUMIDITY,
    _DEPRECATED_DEVICE_CLASS_ILLUMINANCE,
    _DEPRECATED_DEVICE_CLASS_MONETARY,
    _DEPRECATED_DEVICE_CLASS_NITROGEN_DIOXIDE,
    _DEPRECATED_DEVICE_CLASS_NITROGEN_MONOXIDE,
    _DEPRECATED_DEVICE_CLASS_NITROUS_OXIDE,
    _DEPRECATED_DEVICE_CLASS_OZONE,
    _DEPRECATED_DEVICE_CLASS_PM1,
    _DEPRECATED_DEVICE_CLASS_PM10,
    _DEPRECATED_DEVICE_CLASS_PM25,
    _DEPRECATED_DEVICE_CLASS_POWER,
    _DEPRECATED_DEVICE_CLASS_POWER_FACTOR,
    _DEPRECATED_DEVICE_CLASS_PRESSURE,
    _DEPRECATED_DEVICE_CLASS_SIGNAL_STRENGTH,
    _DEPRECATED_DEVICE_CLASS_SULPHUR_DIOXIDE,
    _DEPRECATED_DEVICE_CLASS_TEMPERATURE,
    _DEPRECATED_DEVICE_CLASS_TIMESTAMP,
    _DEPRECATED_DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    _DEPRECATED_DEVICE_CLASS_VOLTAGE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_UNIT_OF_MEASUREMENT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.config_validation import (
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.deprecation import (
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import UNDEFINED, ConfigType, StateType, UndefinedType
from homeassistant.util import dt as dt_util
from homeassistant.util.enum import try_parse_enum

from . import group as group_pre_import  # noqa: F401
from .const import (  # noqa: F401
    _DEPRECATED_STATE_CLASS_MEASUREMENT,
    _DEPRECATED_STATE_CLASS_TOTAL,
    _DEPRECATED_STATE_CLASS_TOTAL_INCREASING,
    ATTR_LAST_RESET,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    CONF_STATE_CLASS,
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    DEVICE_CLASSES,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    NON_NUMERIC_DEVICE_CLASSES,
    STATE_CLASSES,
    STATE_CLASSES_SCHEMA,
    UNIT_CONVERTERS,
    SensorDeviceClass,
    SensorStateClass,
)
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER: Final = logging.getLogger(__name__)

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

SCAN_INTERVAL: Final = timedelta(seconds=30)

__all__ = [
    "ATTR_LAST_RESET",
    "ATTR_OPTIONS",
    "ATTR_STATE_CLASS",
    "CONF_STATE_CLASS",
    "DEVICE_CLASS_STATE_CLASSES",
    "DOMAIN",
    "PLATFORM_SCHEMA_BASE",
    "PLATFORM_SCHEMA",
    "RestoreSensor",
    "SensorDeviceClass",
    "SensorEntity",
    "SensorEntityDescription",
    "SensorExtraStoredData",
    "SensorStateClass",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent[SensorEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    async_setup_ws_api(hass)
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


class SensorEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes sensor entities."""

    device_class: SensorDeviceClass | None = None
    last_reset: datetime | None = None
    native_unit_of_measurement: str | None = None
    options: list[str] | None = None
    state_class: SensorStateClass | str | None = None
    suggested_display_precision: int | None = None
    suggested_unit_of_measurement: str | None = None
    unit_of_measurement: None = None  # Type override, use native_unit_of_measurement


def _numeric_state_expected(
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | str | None,
    native_unit_of_measurement: str | None,
    suggested_display_precision: int | None,
) -> bool:
    """Return true if the sensor must be numeric."""
    # Note: the order of the checks needs to be kept aligned
    # with the checks in `state` property.
    if device_class in NON_NUMERIC_DEVICE_CLASSES:
        return False
    if (
        state_class is not None
        or native_unit_of_measurement is not None
        or suggested_display_precision is not None
    ):
        return True
    # Sensors with custom device classes will have the device class
    # converted to None and are not considered numeric
    return device_class is not None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "last_reset",
    "native_unit_of_measurement",
    "native_value",
    "options",
    "state_class",
    "suggested_display_precision",
    "suggested_unit_of_measurement",
}

TEMPERATURE_UNITS = {UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT}


class SensorEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for sensor entities."""

    _entity_component_unrecorded_attributes = frozenset({ATTR_OPTIONS})

    entity_description: SensorEntityDescription
    _attr_device_class: SensorDeviceClass | None
    _attr_last_reset: datetime | None
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: StateType | date | datetime | Decimal = None
    _attr_options: list[str] | None
    _attr_state_class: SensorStateClass | str | None
    _attr_state: None = None  # Subclasses of SensorEntity should not set this
    _attr_suggested_display_precision: int | None
    _attr_suggested_unit_of_measurement: str | None
    _attr_unit_of_measurement: None = (
        None  # Subclasses of SensorEntity should not set this
    )
    _invalid_state_class_reported = False
    _invalid_unit_of_measurement_reported = False
    _last_reset_reported = False
    _sensor_option_display_precision: int | None = None
    _sensor_option_unit_of_measurement: str | None | UndefinedType = UNDEFINED
    _invalid_suggested_unit_of_measurement_reported = False

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform.

        Allows integrations to remove legacy custom unit conversion which is no longer
        needed without breaking existing sensors. Only works for sensors which are in
        the entity registry.

        This can be removed once core integrations have dropped unneeded custom unit
        conversion.
        """
        super().add_to_platform_start(hass, platform, parallel_updates)

        # Bail out if the sensor doesn't have a unique_id or a device class
        if self.unique_id is None or self.device_class is None:
            return
        registry = er.async_get(self.hass)

        # Bail out if the entity is not yet registered
        if not (
            entity_id := registry.async_get_entity_id(
                platform.domain, platform.platform_name, self.unique_id
            )
        ):
            # Prime _sensor_option_unit_of_measurement to ensure the correct unit
            # is stored in the entity registry.
            self._sensor_option_unit_of_measurement = self._get_initial_suggested_unit()
            return

        registry_entry = registry.async_get(entity_id)
        assert registry_entry

        # Prime _sensor_option_unit_of_measurement to ensure the correct unit
        # is stored in the entity registry.
        self.registry_entry = registry_entry
        self._async_read_entity_options()

        # If the sensor has 'unit_of_measurement' in its sensor options, the user has
        # overridden the unit.
        # If the sensor has 'sensor.private' in its entity options, it already has a
        # suggested_unit.
        registry_unit = registry_entry.unit_of_measurement
        if (
            (
                (sensor_options := registry_entry.options.get(DOMAIN))
                and CONF_UNIT_OF_MEASUREMENT in sensor_options
            )
            or f"{DOMAIN}.private" in registry_entry.options
            or self.unit_of_measurement == registry_unit
        ):
            return

        # Make sure we can convert the units
        if (
            (unit_converter := UNIT_CONVERTERS.get(self.device_class)) is None
            or registry_unit not in unit_converter.VALID_UNITS
            or self.unit_of_measurement not in unit_converter.VALID_UNITS
        ):
            return

        # Set suggested_unit_of_measurement to the old unit to enable automatic
        # conversion
        self.registry_entry = registry.async_update_entity_options(
            entity_id,
            f"{DOMAIN}.private",
            {"suggested_unit_of_measurement": registry_unit},
        )
        # Update _sensor_option_unit_of_measurement to ensure the correct unit
        # is stored in the entity registry.
        self._async_read_entity_options()

    async def async_internal_added_to_hass(self) -> None:
        """Call when the sensor entity is added to hass."""
        await super().async_internal_added_to_hass()
        if self.entity_category == EntityCategory.CONFIG:
            raise HomeAssistantError(
                f"Entity {self.entity_id} cannot be added as the entity category is set to config"
            )

        if not self.registry_entry:
            return
        self._async_read_entity_options()
        self._update_suggested_precision()

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For sensors this is True if the entity has a device class.
        """
        return self.device_class not in (None, SensorDeviceClass.ENUM)

    @cached_property
    @override
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @final
    @property
    def _numeric_state_expected(self) -> bool:
        """Return true if the sensor must be numeric."""
        return _numeric_state_expected(
            try_parse_enum(SensorDeviceClass, self.device_class),
            self.state_class,
            self.native_unit_of_measurement,
            self.suggested_display_precision,
        )

    @cached_property
    def options(self) -> list[str] | None:
        """Return a set of possible options."""
        if hasattr(self, "_attr_options"):
            return self._attr_options
        if hasattr(self, "entity_description"):
            return self.entity_description.options
        return None

    @cached_property
    def state_class(self) -> SensorStateClass | str | None:
        """Return the state class of this entity, if any."""
        if hasattr(self, "_attr_state_class"):
            return self._attr_state_class
        if hasattr(self, "entity_description"):
            return self.entity_description.state_class
        return None

    @cached_property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if hasattr(self, "_attr_last_reset"):
            return self._attr_last_reset
        if hasattr(self, "entity_description"):
            return self.entity_description.last_reset
        return None

    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return the capability attributes."""
        if state_class := self.state_class:
            return {ATTR_STATE_CLASS: state_class}

        if options := self.options:
            return {ATTR_OPTIONS: options}

        return None

    def _is_valid_suggested_unit(self, suggested_unit_of_measurement: str) -> bool:
        """Validate the suggested unit.

        Validate that a unit converter exists for the sensor's device class and that the
        unit converter supports both the native and the suggested units of measurement.
        """
        # Make sure we can convert the units
        if (
            (unit_converter := UNIT_CONVERTERS.get(self.device_class)) is None
            or self.native_unit_of_measurement not in unit_converter.VALID_UNITS
            or suggested_unit_of_measurement not in unit_converter.VALID_UNITS
        ):
            if not self._invalid_suggested_unit_of_measurement_reported:
                self._invalid_suggested_unit_of_measurement_reported = True
                report_issue = self._suggest_report_issue()
                # This should raise in Home Assistant Core 2024.5
                _LOGGER.warning(
                    (
                        "%s sets an invalid suggested_unit_of_measurement. Please %s. "
                        "This warning will become an error in Home Assistant Core 2024.5"
                    ),
                    type(self),
                    report_issue,
                )
            return False

        return True

    def _get_initial_suggested_unit(self) -> str | UndefinedType:
        """Return the initial unit."""
        # Unit suggested by the integration
        suggested_unit_of_measurement = self.suggested_unit_of_measurement

        if suggested_unit_of_measurement is None:
            # Fallback to suggested by the unit conversion rules
            suggested_unit_of_measurement = self.hass.config.units.get_converted_unit(
                self.device_class, self.native_unit_of_measurement
            )

        if suggested_unit_of_measurement is None:
            return UNDEFINED

        # Make sure we can convert the units
        if not self._is_valid_suggested_unit(suggested_unit_of_measurement):
            return UNDEFINED

        return suggested_unit_of_measurement

    def get_initial_entity_options(self) -> er.EntityOptionsType | None:
        """Return initial entity options.

        These will be stored in the entity registry the first time the entity is seen,
        and then only updated if the unit system is changed.
        """
        suggested_unit_of_measurement = self._get_initial_suggested_unit()

        if suggested_unit_of_measurement is UNDEFINED:
            return None

        return {
            f"{DOMAIN}.private": {
                "suggested_unit_of_measurement": suggested_unit_of_measurement
            }
        }

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        if last_reset := self.last_reset:
            state_class = self.state_class
            if state_class != SensorStateClass.TOTAL:
                raise ValueError(
                    f"Entity {self.entity_id} ({type(self)}) with state_class {state_class}"
                    " has set last_reset. Setting last_reset for entities with state_class"
                    " other than 'total' is not supported. Please update your configuration"
                    " if state_class is manually configured."
                )

            if state_class == SensorStateClass.TOTAL:
                return {ATTR_LAST_RESET: last_reset.isoformat()}

        return None

    @cached_property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self._attr_native_value

    @cached_property
    def suggested_display_precision(self) -> int | None:
        """Return the suggested number of decimal digits for display."""
        if hasattr(self, "_attr_suggested_display_precision"):
            return self._attr_suggested_display_precision
        if hasattr(self, "entity_description"):
            return self.entity_description.suggested_display_precision
        return None

    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if hasattr(self, "_attr_native_unit_of_measurement"):
            return self._attr_native_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    @cached_property
    def suggested_unit_of_measurement(self) -> str | None:
        """Return the unit which should be used for the sensor's state.

        This can be used by integrations to override automatic unit conversion rules,
        for example to make a temperature sensor display in °C even if the configured
        unit system prefers °F.

        For sensors without a `unique_id`, this takes precedence over legacy
        temperature conversion rules only.

        For sensors with a `unique_id`, this is applied only if the unit is not set by
        the user, and takes precedence over automatic device-class conversion rules.

        Note:
            suggested_unit_of_measurement is stored in the entity registry the first
            time the entity is seen, and then never updated.

        """
        if hasattr(self, "_attr_suggested_unit_of_measurement"):
            return self._attr_suggested_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.suggested_unit_of_measurement
        return None

    @final
    @property
    @override
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, after unit conversion."""
        # Highest priority, for registered entities: unit set by user,with fallback to
        # unit suggested by integration or secondary fallback to unit conversion rules
        if self._sensor_option_unit_of_measurement is not UNDEFINED:
            return self._sensor_option_unit_of_measurement

        native_unit_of_measurement = self.native_unit_of_measurement

        # Second priority, for non registered entities: unit suggested by integration
        if not self.registry_entry and (
            suggested_unit_of_measurement := self.suggested_unit_of_measurement
        ):
            if self._is_valid_suggested_unit(suggested_unit_of_measurement):
                return suggested_unit_of_measurement

        # Third priority: Legacy temperature conversion, which applies
        # to both registered and non registered entities
        if (
            native_unit_of_measurement in TEMPERATURE_UNITS
            and self.device_class is SensorDeviceClass.TEMPERATURE
        ):
            return self.hass.config.units.temperature_unit

        # Fourth priority: Native unit
        return native_unit_of_measurement

    @final
    @property
    @override
    def state(self) -> Any:
        """Return the state of the sensor and perform unit conversions, if needed."""
        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        value = self.native_value
        # For the sake of validation, we can ignore custom device classes
        # (customization and legacy style translations)
        device_class = try_parse_enum(SensorDeviceClass, self.device_class)
        state_class = self.state_class

        # Sensors with device classes indicating a non-numeric value
        # should not have a unit of measurement
        if device_class in NON_NUMERIC_DEVICE_CLASSES and unit_of_measurement:
            raise ValueError(
                f"Sensor {self.entity_id} has a unit of measurement and thus "
                "indicating it has a numeric value; however, it has the "
                f"non-numeric device class: {device_class}"
            )

        # Validate state class for sensors with a device class
        if (
            state_class
            and not self._invalid_state_class_reported
            and device_class
            and (classes := DEVICE_CLASS_STATE_CLASSES.get(device_class)) is not None
            and state_class not in classes
        ):
            self._invalid_state_class_reported = True
            report_issue = self._suggest_report_issue()

            # This should raise in Home Assistant Core 2023.6
            _LOGGER.warning(
                "Entity %s (%s) is using state class '%s' which "
                "is impossible considering device class ('%s') it is using; "
                "expected %s%s; "
                "Please update your configuration if your entity is manually "
                "configured, otherwise %s",
                self.entity_id,
                type(self),
                state_class,
                device_class,
                "None or one of " if classes else "None",
                ", ".join(f"'{value.value}'" for value in classes),
                report_issue,
            )

        # Checks below only apply if there is a value
        if value is None:
            return None

        # Received a datetime
        if device_class is SensorDeviceClass.TIMESTAMP:
            try:
                # We cast the value, to avoid using isinstance, but satisfy
                # typechecking. The errors are guarded in this try.
                value = cast(datetime, value)
                if value.tzinfo is None:
                    raise ValueError(
                        f"Invalid datetime: {self.entity_id} provides state '{value}', "
                        "which is missing timezone information"
                    )

                if value.tzinfo != UTC:
                    value = value.astimezone(UTC)

                return value.isoformat(timespec="seconds")
            except (AttributeError, OverflowError, TypeError) as err:
                raise ValueError(
                    f"Invalid datetime: {self.entity_id} has timestamp device class "
                    f"but provides state {value}:{type(value)} resulting in '{err}'"
                ) from err

        # Received a date value
        if device_class is SensorDeviceClass.DATE:
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

        # Enum checks
        if (
            options := self.options
        ) is not None or device_class is SensorDeviceClass.ENUM:
            if device_class is not SensorDeviceClass.ENUM:
                reason = "is missing the enum device class"
                if device_class is not None:
                    reason = f"has device class '{device_class}' instead of 'enum'"
                raise ValueError(
                    f"Sensor {self.entity_id} is providing enum options, but {reason}"
                )

            if options and value not in options:
                raise ValueError(
                    f"Sensor {self.entity_id} provides state value '{value}', "
                    "which is not in the list of options provided"
                )
            return value

        suggested_precision = self.suggested_display_precision

        # If the sensor has neither a device class, a state class, a unit of measurement
        # nor a precision then there are no further checks or conversions
        if not _numeric_state_expected(
            device_class, state_class, native_unit_of_measurement, suggested_precision
        ):
            return value

        # From here on a numerical value is expected
        numerical_value: int | float | Decimal
        if not isinstance(value, (int, float, Decimal)):
            try:
                if isinstance(value, str) and "." not in value and "e" not in value:
                    try:
                        numerical_value = int(value)
                    except ValueError:
                        # Handle nan, inf
                        numerical_value = float(value)
                else:
                    numerical_value = float(value)  # type:ignore[arg-type]
            except (TypeError, ValueError) as err:
                raise ValueError(
                    f"Sensor {self.entity_id} has device class '{device_class}', "
                    f"state class '{state_class}' unit '{unit_of_measurement}' and "
                    f"suggested precision '{suggested_precision}' thus indicating it "
                    f"has a numeric value; however, it has the non-numeric value: "
                    f"'{value}' ({type(value)})"
                ) from err
        else:
            numerical_value = value

        if not isfinite(numerical_value):
            raise ValueError(
                f"Sensor {self.entity_id} has device class '{device_class}', "
                f"state class '{state_class}' unit '{unit_of_measurement}' and "
                f"suggested precision '{suggested_precision}' thus indicating it "
                f"has a numeric value; however, it has the non-finite value: "
                f"'{numerical_value}'"
            )

        if native_unit_of_measurement != unit_of_measurement and (
            converter := UNIT_CONVERTERS.get(device_class)
        ):
            # Unit conversion needed
            converted_numerical_value = converter.converter_factory(
                native_unit_of_measurement,
                unit_of_measurement,
            )(float(numerical_value))

            # If unit conversion is happening, and there's no rounding for display,
            # do a best effort rounding here.
            if (
                suggested_precision is None
                and self._sensor_option_display_precision is None
            ):
                # Deduce the precision by finding the decimal point, if any
                value_s = str(value)
                precision = (
                    len(value_s) - value_s.index(".") - 1 if "." in value_s else 0
                )

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
                precision = precision + floor(ratio_log)

                value = f"{converted_numerical_value:z.{precision}f}"
            else:
                value = converted_numerical_value

        # Validate unit of measurement used for sensors with a device class
        if (
            not self._invalid_unit_of_measurement_reported
            and device_class
            and (units := DEVICE_CLASS_UNITS.get(device_class)) is not None
            and native_unit_of_measurement not in units
        ):
            self._invalid_unit_of_measurement_reported = True
            report_issue = self._suggest_report_issue()

            # This should raise in Home Assistant Core 2023.6
            _LOGGER.warning(
                (
                    "Entity %s (%s) is using native unit of measurement '%s' which "
                    "is not a valid unit for the device class ('%s') it is using; "
                    "expected one of %s; "
                    "Please update your configuration if your entity is manually "
                    "configured, otherwise %s"
                ),
                self.entity_id,
                type(self),
                native_unit_of_measurement,
                device_class,
                [str(unit) if unit else "no unit of measurement" for unit in units],
                report_issue,
            )

        return value

    def _display_precision_or_none(self) -> int | None:
        """Return display precision, or None if not set."""
        assert self.registry_entry
        if not (sensor_options := self.registry_entry.options.get(DOMAIN)):
            return None

        for option in ("display_precision", "suggested_display_precision"):
            if (precision := sensor_options.get(option)) is not None:
                return cast(int, precision)
        return None

    def _update_suggested_precision(self) -> None:
        """Update suggested display precision stored in registry."""
        assert self.registry_entry

        device_class = self.device_class
        display_precision = self.suggested_display_precision
        default_unit_of_measurement = (
            self.suggested_unit_of_measurement or self.native_unit_of_measurement
        )
        unit_of_measurement = self.unit_of_measurement

        if (
            display_precision is not None
            and default_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERTERS
        ):
            converter = UNIT_CONVERTERS[device_class]

            # Scale the precision when converting to a larger or smaller unit
            # For example 1.1 Wh should be rendered as 0.0011 kWh, not 0.0 kWh
            ratio_log = log10(
                converter.get_unit_ratio(
                    default_unit_of_measurement, unit_of_measurement
                )
            )
            ratio_log = floor(ratio_log) if ratio_log > 0 else ceil(ratio_log)
            display_precision = max(0, display_precision + ratio_log)

        sensor_options: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN, {})
        if (
            "suggested_display_precision" in sensor_options
            and sensor_options["suggested_display_precision"] == display_precision
        ):
            return

        registry = er.async_get(self.hass)
        sensor_options = dict(sensor_options)
        sensor_options.pop("suggested_display_precision", None)
        if display_precision is not None:
            sensor_options["suggested_display_precision"] = display_precision
        registry.async_update_entity_options(
            self.entity_id, DOMAIN, sensor_options or None
        )

    def _custom_unit_or_undef(
        self, primary_key: str, secondary_key: str
    ) -> str | None | UndefinedType:
        """Return a custom unit, or UNDEFINED if not compatible with the native unit."""
        assert self.registry_entry
        if (
            (sensor_options := self.registry_entry.options.get(primary_key))
            and secondary_key in sensor_options
            and (device_class := self.device_class) in UNIT_CONVERTERS
            and self.native_unit_of_measurement
            in UNIT_CONVERTERS[device_class].VALID_UNITS
            and (custom_unit := sensor_options[secondary_key])
            in UNIT_CONVERTERS[device_class].VALID_UNITS
        ):
            return cast(str, custom_unit)
        return UNDEFINED

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._async_read_entity_options()
        self._update_suggested_precision()

    @callback
    def _async_read_entity_options(self) -> None:
        """Read entity options from entity registry.

        Called when the entity registry entry has been updated and before the sensor is
        added to the state machine.
        """
        self._sensor_option_display_precision = self._display_precision_or_none()
        assert self.registry_entry
        if (
            sensor_options := self.registry_entry.options.get(f"{DOMAIN}.private")
        ) and "refresh_initial_entity_options" in sensor_options:
            registry = er.async_get(self.hass)
            initial_options = self.get_initial_entity_options() or {}
            registry.async_update_entity_options(
                self.registry_entry.entity_id,
                f"{DOMAIN}.private",
                initial_options.get(f"{DOMAIN}.private"),
            )
        self._sensor_option_unit_of_measurement = self._custom_unit_or_undef(
            DOMAIN, CONF_UNIT_OF_MEASUREMENT
        )
        if self._sensor_option_unit_of_measurement is UNDEFINED:
            self._sensor_option_unit_of_measurement = self._custom_unit_or_undef(
                f"{DOMAIN}.private", "suggested_unit_of_measurement"
            )


@dataclass
class SensorExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    native_value: StateType | date | datetime | Decimal
    native_unit_of_measurement: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""
        native_value: StateType | date | datetime | Decimal | dict[str, str] = (
            self.native_value
        )
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
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
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
            # native_value couldn't be returned from decimal_str
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


@callback
def async_update_suggested_units(hass: HomeAssistant) -> None:
    """Update the suggested_unit_of_measurement according to the unit system."""
    registry = er.async_get(hass)

    for entry in registry.entities.values():
        if entry.domain != DOMAIN:
            continue

        sensor_private_options = dict(entry.options.get(f"{DOMAIN}.private", {}))
        sensor_private_options["refresh_initial_entity_options"] = True
        registry.async_update_entity_options(
            entry.entity_id,
            f"{DOMAIN}.private",
            sensor_private_options,
        )


def _display_precision(hass: HomeAssistant, entity_id: str) -> int | None:
    """Return the display precision."""
    if not (entry := er.async_get(hass).async_get(entity_id)) or not (
        sensor_options := entry.options.get(DOMAIN)
    ):
        return None
    if (display_precision := sensor_options.get("display_precision")) is not None:
        return cast(int, display_precision)
    return sensor_options.get("suggested_display_precision")


@callback
def async_rounded_state(hass: HomeAssistant, entity_id: str, state: State) -> str:
    """Return the state rounded for presentation."""
    value = state.state
    if (precision := _display_precision(hass, entity_id)) is None:
        return value

    with suppress(TypeError, ValueError):
        numerical_value = float(value)
        value = f"{numerical_value:z.{precision}f}"

    return value


# As we import deprecated constants from the const module, we need to add these two functions
# otherwise this module will be logged for using deprecated constants and not the custom component
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
