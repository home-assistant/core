"""Numeric integration of data coming from a source sensor over time."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation
import logging
from typing import Any, Final, Self

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    RestoreSensor,
    SensorDeviceClass,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_METHOD,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    INTEGRATION_METHODS,
    METHOD_LEFT,
    METHOD_RIGHT,
    METHOD_TRAPEZOIDAL,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID: Final = "source"

# SI Metric prefixes
UNIT_PREFIXES = {None: 1, "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}

# SI Time prefixes
UNIT_TIME = {
    UnitOfTime.SECONDS: 1,
    UnitOfTime.MINUTES: 60,
    UnitOfTime.HOURS: 60 * 60,
    UnitOfTime.DAYS: 24 * 60 * 60,
}

DEFAULT_ROUND = 3

PLATFORM_SCHEMA = vol.All(
    cv.removed(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
            vol.Optional(CONF_UNIT_PREFIX): vol.In(UNIT_PREFIXES),
            vol.Optional(CONF_UNIT_TIME, default=UnitOfTime.HOURS): vol.In(UNIT_TIME),
            vol.Remove(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=METHOD_TRAPEZOIDAL): vol.In(
                INTEGRATION_METHODS
            ),
        }
    ),
)


class _IntegrationMethod(ABC):
    @staticmethod
    def from_name(method_name: str) -> _IntegrationMethod:
        return _NAME_TO_INTEGRATION_METHOD[method_name]()

    @abstractmethod
    def validate_states(
        self, left: State, right: State
    ) -> tuple[Decimal, Decimal] | None:
        """Check state requirements for integration."""

    @abstractmethod
    def calculate_area_with_two_states(
        self, elapsed_time: Decimal, left: Decimal, right: Decimal
    ) -> Decimal:
        """Calculate area given two states."""

    def calculate_area_with_one_state(
        self, elapsed_time: Decimal, constant_state: Decimal
    ) -> Decimal:
        return constant_state * elapsed_time


class _Trapezoidal(_IntegrationMethod):
    def calculate_area_with_two_states(
        self, elapsed_time: Decimal, left: Decimal, right: Decimal
    ) -> Decimal:
        return elapsed_time * (left + right) / 2

    def validate_states(
        self, left: State, right: State
    ) -> tuple[Decimal, Decimal] | None:
        if (left_dec := _decimal_state(left.state)) is None or (
            right_dec := _decimal_state(right.state)
        ) is None:
            return None
        return (left_dec, right_dec)


class _Left(_IntegrationMethod):
    def calculate_area_with_two_states(
        self, elapsed_time: Decimal, left: Decimal, right: Decimal
    ) -> Decimal:
        return self.calculate_area_with_one_state(elapsed_time, left)

    def validate_states(
        self, left: State, right: State
    ) -> tuple[Decimal, Decimal] | None:
        if (left_dec := _decimal_state(left.state)) is None:
            return None
        return (left_dec, left_dec)


class _Right(_IntegrationMethod):
    def calculate_area_with_two_states(
        self, elapsed_time: Decimal, left: Decimal, right: Decimal
    ) -> Decimal:
        return self.calculate_area_with_one_state(elapsed_time, right)

    def validate_states(
        self, left: State, right: State
    ) -> tuple[Decimal, Decimal] | None:
        if (right_dec := _decimal_state(right.state)) is None:
            return None
        return (right_dec, right_dec)


def _decimal_state(state: str) -> Decimal | None:
    try:
        return Decimal(state)
    except (InvalidOperation, TypeError):
        return None


_NAME_TO_INTEGRATION_METHOD: dict[str, type[_IntegrationMethod]] = {
    METHOD_LEFT: _Left,
    METHOD_RIGHT: _Right,
    METHOD_TRAPEZOIDAL: _Trapezoidal,
}


@dataclass
class IntegrationSensorExtraStoredData(SensorExtraStoredData):
    """Object to hold extra stored data."""

    source_entity: str | None
    last_valid_state: Decimal | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the utility sensor data."""
        data = super().as_dict()
        data["source_entity"] = self.source_entity
        data["last_valid_state"] = (
            str(self.last_valid_state) if self.last_valid_state else None
        )
        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored sensor state from a dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None

        source_entity = restored.get(ATTR_SOURCE_ID)

        try:
            last_valid_state = (
                Decimal(str(restored.get("last_valid_state")))
                if restored.get("last_valid_state")
                else None
            )
        except InvalidOperation:
            # last_period is corrupted
            _LOGGER.error("Could not use last_valid_state")
            return None

        if last_valid_state is None:
            return None

        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            source_entity,
            last_valid_state,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Integration - Riemann sum integral config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_SOURCE_SENSOR]
    )

    source_entity = er.EntityRegistry.async_get(registry, source_entity_id)
    dev_reg = dr.async_get(hass)
    # Resolve source entity device
    if (
        (source_entity is not None)
        and (source_entity.device_id is not None)
        and (
            (
                device := dev_reg.async_get(
                    device_id=source_entity.device_id,
                )
            )
            is not None
        )
    ):
        device_info = DeviceInfo(
            identifiers=device.identifiers,
            connections=device.connections,
        )
    else:
        device_info = None

    if (unit_prefix := config_entry.options.get(CONF_UNIT_PREFIX)) == "none":
        # Before we had support for optional selectors, "none" was used for selecting nothing
        unit_prefix = None

    integral = IntegrationSensor(
        integration_method=config_entry.options[CONF_METHOD],
        name=config_entry.title,
        round_digits=int(config_entry.options[CONF_ROUND_DIGITS]),
        source_entity=source_entity_id,
        unique_id=config_entry.entry_id,
        unit_prefix=unit_prefix,
        unit_time=config_entry.options[CONF_UNIT_TIME],
        device_info=device_info,
    )

    async_add_entities([integral])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration sensor."""
    integral = IntegrationSensor(
        integration_method=config[CONF_METHOD],
        name=config.get(CONF_NAME),
        round_digits=config[CONF_ROUND_DIGITS],
        source_entity=config[CONF_SOURCE_SENSOR],
        unique_id=config.get(CONF_UNIQUE_ID),
        unit_prefix=config.get(CONF_UNIT_PREFIX),
        unit_time=config[CONF_UNIT_TIME],
    )

    async_add_entities([integral])


class IntegrationSensor(RestoreSensor):
    """Representation of an integration sensor."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_should_poll = False

    def __init__(
        self,
        *,
        integration_method: str,
        name: str | None,
        round_digits: int,
        source_entity: str,
        unique_id: str | None,
        unit_prefix: str | None,
        unit_time: UnitOfTime,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the integration sensor."""
        self._attr_unique_id = unique_id
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state: Decimal | None = None
        self._method = _IntegrationMethod.from_name(integration_method)

        self._attr_name = name if name is not None else f"{source_entity} integral"
        self._unit_prefix_string = "" if unit_prefix is None else unit_prefix
        self._unit_of_measurement: str | None = None
        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]
        self._unit_time_str = unit_time
        self._attr_icon = "mdi:chart-histogram"
        self._source_entity: str = source_entity
        self._last_valid_state: Decimal | None = None
        self._attr_device_info = device_info

    def _calculate_unit(self, source_unit: str) -> str:
        """Multiply source_unit with time unit of the integral.

        Possibly cancelling out a time unit in the denominator of the source_unit.
        Note that this is a heuristic string manipulation method and might not
        transform all source units in a sensible way.

        Examples:
        - Speed to distance: 'km/h' and 'h' will be transformed to 'km'
        - Power to energy: 'W' and 'h' will be transformed to 'Wh'

        """
        unit_time = self._unit_time_str
        if source_unit.endswith(f"/{unit_time}"):
            integral_unit = source_unit[0 : (-(1 + len(unit_time)))]
        else:
            integral_unit = f"{source_unit}{unit_time}"

        return f"{self._unit_prefix_string}{integral_unit}"

    def _derive_and_set_attributes_from_state(self, source_state: State) -> None:
        source_unit = source_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if source_unit is not None:
            self._unit_of_measurement = self._calculate_unit(source_unit)
        else:
            # If the source has no defined unit we cannot derive a unit for the integral
            self._unit_of_measurement = None

        if (
            self.device_class is None
            and source_state.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.POWER
        ):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_icon = None  # Remove this sensors icon default and allow to fallback to the ENERGY default

    def _update_integral(self, area: Decimal) -> None:
        area_scaled = area / (self._unit_prefix * self._unit_time)
        if isinstance(self._state, Decimal):
            self._state += area_scaled
        else:
            self._state = area_scaled
        _LOGGER.debug(
            "area = %s, area_scaled = %s new state = %s", area, area_scaled, self._state
        )
        self._last_valid_state = self._state

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._state = (
                Decimal(str(last_sensor_data.native_value))
                if last_sensor_data.native_value
                else last_sensor_data.last_valid_state
            )
            self._attr_native_value = last_sensor_data.native_value
            self._unit_of_measurement = last_sensor_data.native_unit_of_measurement
            self._last_valid_state = last_sensor_data.last_valid_state

            _LOGGER.debug(
                "Restored state %s and last_valid_state %s",
                self._state,
                self._last_valid_state,
            )
        elif (state := await self.async_get_last_state()) is not None:
            # legacy to be removed on 2023.10 (we are keeping this to avoid losing data during the transition)
            if state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                if state.state == STATE_UNAVAILABLE:
                    self._attr_available = False
            else:
                try:
                    self._state = Decimal(state.state)
                except (DecimalException, ValueError) as err:
                    _LOGGER.warning(
                        "%s could not restore last state %s: %s",
                        self.entity_id,
                        state.state,
                        err,
                    )

            self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
            self._unit_of_measurement = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._sensor_source_id],
                self._handle_state_change,
            )
        )

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        if old_state is None or new_state is None:
            return

        if new_state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        self._derive_and_set_attributes_from_state(new_state)

        if not (states := self._method.validate_states(old_state, new_state)):
            self.async_write_ha_state()
            return

        elapsed_seconds = Decimal(
            (new_state.last_updated - old_state.last_updated).total_seconds()
        )

        area = self._method.calculate_area_with_two_states(elapsed_seconds, *states)

        self._update_integral(area)
        self.async_write_ha_state()

    @property
    def native_value(self) -> Decimal | None:
        """Return the state of the sensor."""
        if isinstance(self._state, Decimal):
            return round(self._state, self._round_digits)
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the sensor."""
        return {
            ATTR_SOURCE_ID: self._source_entity,
        }

    @property
    def extra_restore_state_data(self) -> IntegrationSensorExtraStoredData:
        """Return sensor specific state data to be restored."""
        return IntegrationSensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            self._source_entity,
            self._last_valid_state,
        )

    async def async_get_last_sensor_data(
        self,
    ) -> IntegrationSensorExtraStoredData | None:
        """Restore Utility Meter Sensor Extra Stored Data."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None

        return IntegrationSensorExtraStoredData.from_dict(
            restored_last_extra_data.as_dict()
        )
