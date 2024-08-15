"""Component to allow numeric input for platforms."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import dataclasses
from datetime import timedelta
from functools import cached_property
import logging
from math import ceil, floor
from typing import TYPE_CHECKING, Any, Self, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, CONF_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    async_get_hass_or_none,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_suggest_report_issue

from .const import (  # noqa: F401
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_STEP_VALIDATION,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    SERVICE_SET_VALUE,
    UNIT_CONVERTERS,
    NumberDeviceClass,
    NumberMode,
)
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


__all__ = [
    "ATTR_MAX",
    "ATTR_MIN",
    "ATTR_STEP",
    "ATTR_VALUE",
    "DEFAULT_MAX_VALUE",
    "DEFAULT_MIN_VALUE",
    "DEFAULT_STEP",
    "DOMAIN",
    "PLATFORM_SCHEMA_BASE",
    "PLATFORM_SCHEMA",
    "NumberDeviceClass",
    "NumberEntity",
    "NumberEntityDescription",
    "NumberExtraStoredData",
    "NumberMode",
    "RestoreNumber",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Number entities."""
    component = hass.data[DOMAIN] = EntityComponent[NumberEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    async_setup_ws_api(hass)
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
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="out_of_range",
            translation_placeholders={
                "value": value,
                "entity_id": entity.entity_id,
                "min_value": str(entity.min_value),
                "max_value": str(entity.max_value),
            },
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


class NumberEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes number entities."""

    device_class: NumberDeviceClass | None = None
    max_value: None = None
    min_value: None = None
    mode: NumberMode | None = None
    native_max_value: float | None = None
    native_min_value: float | None = None
    native_step: float | None = None
    native_unit_of_measurement: str | None = None
    step: None = None
    unit_of_measurement: None = None  # Type override, use native_unit_of_measurement


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


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "native_max_value",
    "native_min_value",
    "native_step",
    "mode",
    "native_unit_of_measurement",
    "native_value",
}


class NumberEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Number entity."""

    _entity_component_unrecorded_attributes = frozenset(
        {ATTR_MIN, ATTR_MAX, ATTR_STEP, ATTR_STEP_VALIDATION, ATTR_MODE}
    )

    entity_description: NumberEntityDescription
    _attr_device_class: NumberDeviceClass | None
    _attr_max_value: None
    _attr_min_value: None
    _attr_mode: NumberMode
    _attr_state: None = None
    _attr_step: None
    _attr_unit_of_measurement: None  # Subclasses of NumberEntity should not set this
    _attr_value: None
    _attr_native_max_value: float
    _attr_native_min_value: float
    _attr_native_step: float
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: float | None = None
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
            report_issue = async_suggest_report_issue(
                async_get_hass_or_none(), module=cls.__module__
            )
            _LOGGER.warning(
                (
                    "%s::%s is overriding deprecated methods on an instance of "
                    "NumberEntity, this is not valid and will be unsupported "
                    "from Home Assistant 2022.10. Please %s"
                ),
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
        device_class = self.device_class
        min_value = self._convert_to_state_value(
            self.native_min_value, floor_decimal, device_class
        )
        max_value = self._convert_to_state_value(
            self.native_max_value, ceil_decimal, device_class
        )
        return {
            ATTR_MIN: min_value,
            ATTR_MAX: max_value,
            ATTR_STEP: self._calculate_step(min_value, max_value),
            ATTR_MODE: self.mode,
        }

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For numbers this is True if the entity has a device class.
        """
        return self.device_class is not None

    @cached_property
    def device_class(self) -> NumberDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
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
        return self._convert_to_state_value(
            self.native_min_value, floor_decimal, self.device_class
        )

    @cached_property
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
        return self._convert_to_state_value(
            self.native_max_value, ceil_decimal, self.device_class
        )

    @cached_property
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
        return self._calculate_step(self.min_value, self.max_value)

    def _calculate_step(self, min_value: float, max_value: float) -> float:
        """Return the increment/decrement step."""
        if (native_step := self.native_step) is not None:
            return native_step
        step = DEFAULT_STEP
        value_range = abs(max_value - min_value)
        if value_range != 0:
            while value_range <= step:
                step /= 10.0
        return step

    @cached_property
    def mode(self) -> NumberMode:
        """Return the mode of the entity."""
        if hasattr(self, "_attr_mode"):
            return self._attr_mode
        if (
            hasattr(self, "entity_description")
            and self.entity_description.mode is not None
        ):
            return self.entity_description.mode
        return NumberMode.AUTO

    @property
    @final
    def state(self) -> float | None:
        """Return the entity state."""
        return self.value

    @cached_property
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

        native_unit_of_measurement = self.native_unit_of_measurement
        # device_class is checked after native_unit_of_measurement since most
        # of the time we can avoid the device_class check
        if (
            native_unit_of_measurement
            in (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT)
            and self.device_class == NumberDeviceClass.TEMPERATURE
        ):
            return self.hass.config.units.temperature_unit

        return native_unit_of_measurement

    @cached_property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._attr_native_value

    @property
    @final
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if (native_value := self.native_value) is None:
            return native_value
        return self._convert_to_state_value(native_value, round, self.device_class)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_native_value, value)

    @final
    def set_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError

    @final
    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_value, value)

    def _convert_to_state_value(
        self,
        value: float,
        method: Callable[[float, int], float],
        device_class: NumberDeviceClass | None,
    ) -> float:
        """Convert a value in the number's native unit to the configured unit."""
        # device_class is checked first since most of the time we can avoid
        # the unit conversion
        if device_class not in UNIT_CONVERTERS:
            return value

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        if native_unit_of_measurement != unit_of_measurement:
            if TYPE_CHECKING:
                assert native_unit_of_measurement
                assert unit_of_measurement

            value_s = str(value)
            prec = len(value_s) - value_s.index(".") - 1 if "." in value_s else 0

            # Suppress ValueError (Could not convert value to float)
            with suppress(ValueError):
                value_new: float = UNIT_CONVERTERS[device_class].converter_factory(
                    native_unit_of_measurement,
                    unit_of_measurement,
                )(value)

                # Round to the wanted precision
                return method(value_new, prec)

        return value

    def convert_to_native_value(self, value: float) -> float:
        """Convert a value to the number's native unit."""
        # device_class is checked first since most of the time we can avoid
        # the unit conversion
        if value is None or (device_class := self.device_class) not in UNIT_CONVERTERS:
            return value

        native_unit_of_measurement = self.native_unit_of_measurement
        unit_of_measurement = self.unit_of_measurement
        if native_unit_of_measurement != unit_of_measurement:
            if TYPE_CHECKING:
                assert native_unit_of_measurement
                assert unit_of_measurement

            return UNIT_CONVERTERS[device_class].converter_factory(
                unit_of_measurement,
                native_unit_of_measurement,
            )(value)

        return value

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        if TYPE_CHECKING:
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
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
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
