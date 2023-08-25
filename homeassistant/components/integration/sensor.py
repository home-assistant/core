"""Numeric integration of data coming from a source sensor over time."""
from __future__ import annotations

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

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
            vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
            vol.Optional(CONF_UNIT_TIME, default=UnitOfTime.HOURS): vol.In(UNIT_TIME),
            vol.Remove(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=METHOD_TRAPEZOIDAL): vol.In(
                INTEGRATION_METHODS
            ),
        }
    ),
)


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

    unit_prefix = config_entry.options[CONF_UNIT_PREFIX]
    if unit_prefix == "none":
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
        unit_prefix=config[CONF_UNIT_PREFIX],
        unit_time=config[CONF_UNIT_TIME],
    )

    async_add_entities([integral])


# pylint: disable-next=hass-invalid-inheritance # needs fixing
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
        self._method = integration_method

        self._attr_name = name if name is not None else f"{source_entity} integral"
        self._unit_template = f"{'' if unit_prefix is None else unit_prefix}{{}}"
        self._unit_of_measurement: str | None = None
        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]
        self._unit_time_str = unit_time
        self._attr_icon = "mdi:chart-histogram"
        self._source_entity: str = source_entity
        self._last_valid_state: Decimal | None = None
        self._attr_device_info = device_info

    def _unit(self, source_unit: str) -> str:
        """Derive unit from the source sensor, SI prefix and time unit."""
        unit_time = self._unit_time_str
        if source_unit.endswith(f"/{unit_time}"):
            integral_unit = source_unit[0 : (-(1 + len(unit_time)))]
        else:
            integral_unit = f"{source_unit}{unit_time}"

        return self._unit_template.format(integral_unit)

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
            self.async_write_ha_state()
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
            self.async_write_ha_state()

        @callback
        def calc_integration(event: EventType[EventStateChangedData]) -> None:
            """Handle the sensor state changes."""
            old_state = event.data["old_state"]
            new_state = event.data["new_state"]

            # We may want to update our state before an early return,
            # based on the source sensor's unit_of_measurement
            # or device_class.
            update_state = False

            if (
                source_state := self.hass.states.get(self._sensor_source_id)
            ) is None or source_state.state == STATE_UNAVAILABLE:
                self._attr_available = False
                update_state = True
            else:
                self._attr_available = True

            if old_state is None or new_state is None:
                # we can't calculate the elapsed time, so we can't calculate the integral
                return

            unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if unit is not None:
                new_unit_of_measurement = self._unit(unit)
                if self._unit_of_measurement != new_unit_of_measurement:
                    self._unit_of_measurement = new_unit_of_measurement
                    update_state = True

            if (
                self.device_class is None
                and new_state.attributes.get(ATTR_DEVICE_CLASS)
                == SensorDeviceClass.POWER
            ):
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_icon = None
                update_state = True

            if update_state:
                self.async_write_ha_state()

            try:
                # integration as the Riemann integral of previous measures.
                elapsed_time = (
                    new_state.last_updated - old_state.last_updated
                ).total_seconds()

                if (
                    self._method == METHOD_TRAPEZOIDAL
                    and new_state.state
                    not in (
                        STATE_UNKNOWN,
                        STATE_UNAVAILABLE,
                    )
                    and old_state.state
                    not in (
                        STATE_UNKNOWN,
                        STATE_UNAVAILABLE,
                    )
                ):
                    area = (
                        (Decimal(new_state.state) + Decimal(old_state.state))
                        * Decimal(elapsed_time)
                        / 2
                    )
                elif self._method == METHOD_LEFT and old_state.state not in (
                    STATE_UNKNOWN,
                    STATE_UNAVAILABLE,
                ):
                    area = Decimal(old_state.state) * Decimal(elapsed_time)
                elif self._method == METHOD_RIGHT and new_state.state not in (
                    STATE_UNKNOWN,
                    STATE_UNAVAILABLE,
                ):
                    area = Decimal(new_state.state) * Decimal(elapsed_time)
                else:
                    _LOGGER.debug(
                        "Could not apply method %s to %s -> %s",
                        self._method,
                        old_state.state,
                        new_state.state,
                    )
                    return

                integral = area / (self._unit_prefix * self._unit_time)
                _LOGGER.debug(
                    "area = %s, integral = %s state = %s", area, integral, self._state
                )
                assert isinstance(integral, Decimal)
            except ValueError as err:
                _LOGGER.warning("While calculating integration: %s", err)
            except DecimalException as err:
                _LOGGER.warning(
                    "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
                )
            except AssertionError as err:
                _LOGGER.error("Could not calculate integral: %s", err)
            else:
                if isinstance(self._state, Decimal):
                    self._state += integral
                else:
                    self._state = integral
                self._last_valid_state = self._state
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._sensor_source_id], calc_integration
            )
        )

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
        state_attr = {
            ATTR_SOURCE_ID: self._source_entity,
        }

        return state_attr

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
