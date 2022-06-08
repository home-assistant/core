"""Component to allow numeric input for platforms."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import inspect
import logging
from math import ceil, floor
from typing import Any, Callable, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import temperature as temperature_util

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

    # temperature (C/F)
    TEMPERATURE = "temperature"


class NumberMode(StrEnum):
    """Modes for number entities."""

    AUTO = "auto"
    BOX = "box"
    SLIDER = "slider"


UNIT_CONVERSIONS: dict[str, Callable[[float, str, str], float]] = {
    NumberDeviceClass.TEMPERATURE: temperature_util.convert,
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Number entities."""
    component = hass.data[DOMAIN] = EntityComponent(
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
        # pylint: disable-next=protected-access
        native_value = entity._convert_to_native_value(value)
        # Clamp to the native range
        native_value = min(
            max(native_value, entity.native_min_value), entity.native_max_value
        )
        await entity.async_set_native_value(native_value)
    except NotImplementedError:
        await entity.async_set_value(value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
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
                "%s is setting deprecated attributes on an instance of "
                "NumberEntityDescription, this is not valid and will be unsupported "
                "from Home Assistant 2022.10. Please %s",
                module.__name__,
                report_issue,
            )
            self.native_unit_of_measurement = self.unit_of_measurement


def ceil_decimal(value: float, precision: float = 0) -> float:
    """Return the ceiling of f with d decimals.

    This is a simple implementation which ignores floating point inexactness.
    """
    if precision == 0:
        return ceil(value)
    factor = 10**precision
    return ceil(value * factor) / factor


def floor_decimal(value: float, precision: float = 0) -> float:
    """Return the floor of f with d decimals.

    This is a simple implementation which ignores floating point inexactness.
    """
    if precision == 0:
        return floor(value)
    factor = 10**precision
    return floor(value * factor) / factor


class NumberEntity(Entity):
    """Representation of a Number entity."""

    entity_description: NumberEntityDescription
    _attr_max_value: None
    _attr_min_value: None
    _attr_state: None = None
    _attr_step: None
    _attr_mode: NumberMode = NumberMode.AUTO
    _attr_value: None
    _attr_native_max_value: float
    _attr_native_min_value: float
    _attr_native_step: float
    _attr_native_value: float
    _attr_native_unit_of_measurement: str | None
    _attr_unit_of_measurement: None = (
        None  # Subclasses of NumberEntity should not set this
    )
    _deprecated_number_entity_reported = False

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
        if hasattr(self, "_attr_native_step"):
            return self._attr_native_step
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
        native_unit_of_measurement = self.native_unit_of_measurement

        if (
            self.device_class == NumberDeviceClass.TEMPERATURE
            and native_unit_of_measurement in (TEMP_CELSIUS, TEMP_FAHRENHEIT)
        ):
            return self.hass.config.units.temperature_unit

        return native_unit_of_measurement

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
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

    def _convert_to_state_value(self, value: float, method: Callable) -> float:

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        device_class = self.device_class

        if (
            native_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERSIONS
        ):
            assert native_unit_of_measurement
            assert unit_of_measurement

            value_s = str(value)
            prec = len(value_s) - value_s.index(".") - 1 if "." in value_s else 0

            # Suppress ValueError (Could not convert value to float)
            with suppress(ValueError):
                value_new: float = UNIT_CONVERSIONS[device_class](
                    value_new,
                    native_unit_of_measurement,
                    unit_of_measurement,
                )

                # Round to the wanted precision
                value = method(value_new) if prec == 0 else method(value_new, prec)

        return value

    def _convert_to_native_value(self, value: float) -> float:

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        device_class = self.device_class

        if (
            value is not None
            and native_unit_of_measurement != unit_of_measurement
            and device_class in UNIT_CONVERSIONS
        ):
            assert native_unit_of_measurement
            assert unit_of_measurement

            value = UNIT_CONVERSIONS[device_class](
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
                "Entity %s (%s) is using deprecated NumberEntity features, please %s",
                self.entity_id,
                type(self),
                report_issue,
            )
