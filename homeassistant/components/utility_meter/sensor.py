"""Utility meter from sensors providing raw data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException, InvalidOperation
import logging
from typing import Any, Self

from croniter import croniter
import voluptuous as vol

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    RestoreSensor,
    SensorDeviceClass,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import _suggest_report_issue
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.template import is_number
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_CRON_PATTERN,
    ATTR_VALUE,
    BIMONTHLY,
    CONF_CRON_PATTERN,
    CONF_METER,
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_PERIODICALLY_RESETTING,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
    CONF_TARIFFS,
    DAILY,
    DATA_TARIFF_SENSORS,
    DATA_UTILITY,
    HOURLY,
    MONTHLY,
    QUARTER_HOURLY,
    QUARTERLY,
    SERVICE_CALIBRATE_METER,
    SIGNAL_RESET_METER,
    WEEKLY,
    YEARLY,
)

PERIOD2CRON = {
    QUARTER_HOURLY: "{minute}/15 * * * *",
    HOURLY: "{minute} * * * *",
    DAILY: "{minute} {hour} * * *",
    WEEKLY: "{minute} {hour} * * {day}",
    MONTHLY: "{minute} {hour} {day} * *",
    BIMONTHLY: "{minute} {hour} {day} */2 *",
    QUARTERLY: "{minute} {hour} {day} */3 *",
    YEARLY: "{minute} {hour} {day} 1/12 *",
}

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"
ATTR_STATUS = "status"
ATTR_PERIOD = "meter_period"
ATTR_LAST_PERIOD = "last_period"
ATTR_LAST_VALID_STATE = "last_valid_state"
ATTR_TARIFF = "tariff"

DEVICE_CLASS_MAP = {
    UnitOfEnergy.WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
}


PRECISION = 3
PAUSED = "paused"
COLLECTING = "collecting"


def validate_is_number(value):
    """Validate value is a number."""
    if is_number(value):
        return value
    raise vol.Invalid("Value is not a number")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Utility Meter config entry."""
    entry_id = config_entry.entry_id
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_SOURCE_SENSOR]
    )

    source_entity = registry.async_get(source_entity_id)
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

    cron_pattern = None
    delta_values = config_entry.options[CONF_METER_DELTA_VALUES]
    meter_offset = timedelta(days=config_entry.options[CONF_METER_OFFSET])
    meter_type = config_entry.options[CONF_METER_TYPE]
    if meter_type == "none":
        meter_type = None
    name = config_entry.title
    net_consumption = config_entry.options[CONF_METER_NET_CONSUMPTION]
    periodically_resetting = config_entry.options[CONF_METER_PERIODICALLY_RESETTING]
    tariff_entity = hass.data[DATA_UTILITY][entry_id][CONF_TARIFF_ENTITY]

    meters = []
    tariffs = config_entry.options[CONF_TARIFFS]

    if not tariffs:
        # Add single sensor, not gated by a tariff selector
        meter_sensor = UtilityMeterSensor(
            cron_pattern=cron_pattern,
            delta_values=delta_values,
            meter_offset=meter_offset,
            meter_type=meter_type,
            name=name,
            net_consumption=net_consumption,
            parent_meter=entry_id,
            periodically_resetting=periodically_resetting,
            source_entity=source_entity_id,
            tariff_entity=tariff_entity,
            tariff=None,
            unique_id=entry_id,
            device_info=device_info,
        )
        meters.append(meter_sensor)
        hass.data[DATA_UTILITY][entry_id][DATA_TARIFF_SENSORS].append(meter_sensor)
    else:
        # Add sensors for each tariff
        for tariff in tariffs:
            meter_sensor = UtilityMeterSensor(
                cron_pattern=cron_pattern,
                delta_values=delta_values,
                meter_offset=meter_offset,
                meter_type=meter_type,
                name=f"{name} {tariff}",
                net_consumption=net_consumption,
                parent_meter=entry_id,
                periodically_resetting=periodically_resetting,
                source_entity=source_entity_id,
                tariff_entity=tariff_entity,
                tariff=tariff,
                unique_id=f"{entry_id}_{tariff}",
                device_info=device_info,
            )
            meters.append(meter_sensor)
            hass.data[DATA_UTILITY][entry_id][DATA_TARIFF_SENSORS].append(meter_sensor)

    async_add_entities(meters)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_CALIBRATE_METER,
        {vol.Required(ATTR_VALUE): validate_is_number},
        "async_calibrate",
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the utility meter sensor."""
    if discovery_info is None:
        _LOGGER.error(
            "This platform is not available to configure "
            "from 'sensor:' in configuration.yaml"
        )
        return

    meters = []
    for conf in discovery_info.values():
        meter = conf[CONF_METER]
        conf_meter_source = hass.data[DATA_UTILITY][meter][CONF_SOURCE_SENSOR]
        conf_meter_unique_id = hass.data[DATA_UTILITY][meter].get(CONF_UNIQUE_ID)
        conf_sensor_tariff = conf.get(CONF_TARIFF, "single_tariff")
        conf_sensor_unique_id = (
            f"{conf_meter_unique_id}_{conf_sensor_tariff}"
            if conf_meter_unique_id
            else None
        )
        conf_meter_name = hass.data[DATA_UTILITY][meter].get(CONF_NAME, meter)
        conf_sensor_tariff = conf.get(CONF_TARIFF)

        suggested_entity_id = None
        if conf_sensor_tariff:
            conf_sensor_name = f"{conf_meter_name} {conf_sensor_tariff}"
            slug = slugify(f"{meter} {conf_sensor_tariff}")
            suggested_entity_id = f"sensor.{slug}"
        else:
            conf_sensor_name = conf_meter_name

        conf_meter_type = hass.data[DATA_UTILITY][meter].get(CONF_METER_TYPE)
        conf_meter_offset = hass.data[DATA_UTILITY][meter][CONF_METER_OFFSET]
        conf_meter_delta_values = hass.data[DATA_UTILITY][meter][
            CONF_METER_DELTA_VALUES
        ]
        conf_meter_net_consumption = hass.data[DATA_UTILITY][meter][
            CONF_METER_NET_CONSUMPTION
        ]
        conf_meter_periodically_resetting = hass.data[DATA_UTILITY][meter][
            CONF_METER_PERIODICALLY_RESETTING
        ]
        conf_meter_tariff_entity = hass.data[DATA_UTILITY][meter].get(
            CONF_TARIFF_ENTITY
        )
        conf_cron_pattern = hass.data[DATA_UTILITY][meter].get(CONF_CRON_PATTERN)
        meter_sensor = UtilityMeterSensor(
            cron_pattern=conf_cron_pattern,
            delta_values=conf_meter_delta_values,
            meter_offset=conf_meter_offset,
            meter_type=conf_meter_type,
            name=conf_sensor_name,
            net_consumption=conf_meter_net_consumption,
            parent_meter=meter,
            periodically_resetting=conf_meter_periodically_resetting,
            source_entity=conf_meter_source,
            tariff_entity=conf_meter_tariff_entity,
            tariff=conf_sensor_tariff,
            unique_id=conf_sensor_unique_id,
            suggested_entity_id=suggested_entity_id,
        )
        meters.append(meter_sensor)

        hass.data[DATA_UTILITY][meter][DATA_TARIFF_SENSORS].append(meter_sensor)

    async_add_entities(meters)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_CALIBRATE_METER,
        {vol.Required(ATTR_VALUE): validate_is_number},
        "async_calibrate",
    )


@dataclass
class UtilitySensorExtraStoredData(SensorExtraStoredData):
    """Object to hold extra stored data."""

    last_period: Decimal
    last_reset: datetime | None
    last_valid_state: Decimal | None
    status: str

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the utility sensor data."""
        data = super().as_dict()
        data["last_period"] = str(self.last_period)
        if isinstance(self.last_reset, (datetime)):
            data["last_reset"] = self.last_reset.isoformat()
        data["last_valid_state"] = (
            str(self.last_valid_state) if self.last_valid_state else None
        )
        data["status"] = self.status

        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored sensor state from a dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None

        try:
            last_period: Decimal = Decimal(restored["last_period"])
            last_reset: datetime | None = dt_util.parse_datetime(restored["last_reset"])
            last_valid_state: Decimal | None = (
                Decimal(restored["last_valid_state"])
                if restored.get("last_valid_state")
                else None
            )
            status: str = restored["status"]
        except KeyError:
            # restored is a dict, but does not have all values
            return None
        except InvalidOperation:
            # last_period is corrupted
            return None

        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            last_period,
            last_reset,
            last_valid_state,
            status,
        )


class UtilityMeterSensor(RestoreSensor):
    """Representation of an utility meter sensor."""

    _attr_icon = "mdi:counter"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        cron_pattern,
        delta_values,
        meter_offset,
        meter_type,
        name,
        net_consumption,
        parent_meter,
        periodically_resetting,
        source_entity,
        tariff_entity,
        tariff,
        unique_id,
        suggested_entity_id=None,
        device_info=None,
    ):
        """Initialize the Utility Meter sensor."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self.entity_id = suggested_entity_id
        self._parent_meter = parent_meter
        self._sensor_source_id = source_entity
        self._state = None
        self._last_period = Decimal(0)
        self._last_reset = dt_util.utcnow()
        self._last_valid_state = None
        self._collecting = None
        self._name = name
        self._unit_of_measurement = None
        self._period = meter_type
        if meter_type is not None:
            # For backwards compatibility reasons we convert the period and offset into a cron pattern
            self._cron_pattern = PERIOD2CRON[meter_type].format(
                minute=meter_offset.seconds % 3600 // 60,
                hour=meter_offset.seconds // 3600,
                day=meter_offset.days + 1,
            )
            _LOGGER.debug("CRON pattern: %s", self._cron_pattern)
        else:
            self._cron_pattern = cron_pattern
        self._sensor_delta_values = delta_values
        self._sensor_net_consumption = net_consumption
        self._sensor_periodically_resetting = periodically_resetting
        self._tariff = tariff
        self._tariff_entity = tariff_entity

    def start(self, unit):
        """Initialize unit and state upon source initial update."""
        self._unit_of_measurement = unit
        self._state = 0
        self.async_write_ha_state()

    @staticmethod
    def _validate_state(state: State | None) -> Decimal | None:
        """Parse the state as a Decimal if available. Throws DecimalException if the state is not a number."""
        try:
            return (
                None
                if state is None or state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]
                else Decimal(state.state)
            )
        except DecimalException:
            return None

    def calculate_adjustment(
        self, old_state: State | None, new_state: State
    ) -> Decimal | None:
        """Calculate the adjustment based on the old and new state."""

        # First check if the new_state is valid (see discussion in PR #88446)
        if (new_state_val := self._validate_state(new_state)) is None:
            _LOGGER.warning("Invalid state %s", new_state.state)
            return None

        if self._sensor_delta_values:
            return new_state_val

        if (
            not self._sensor_periodically_resetting
            and self._last_valid_state is not None
        ):  # Fallback to old_state if sensor is periodically resetting but last_valid_state is None
            return new_state_val - self._last_valid_state

        if (old_state_val := self._validate_state(old_state)) is not None:
            return new_state_val - old_state_val

        _LOGGER.debug(
            "%s received an invalid state change coming from %s (%s > %s)",
            self.name,
            self._sensor_source_id,
            old_state.state if old_state else None,
            new_state_val,
        )
        return None

    @callback
    def async_reading(self, event: EventType[EventStateChangedData]) -> None:
        """Handle the sensor state changes."""
        if (
            source_state := self.hass.states.get(self._sensor_source_id)
        ) is None or source_state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True

        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None:
            return

        # First check if the new_state is valid (see discussion in PR #88446)
        if (new_state_val := self._validate_state(new_state)) is None:
            _LOGGER.warning(
                "%s received an invalid new state from %s : %s",
                self.name,
                self._sensor_source_id,
                new_state.state,
            )
            return

        if self._state is None:
            # First state update initializes the utility_meter sensors
            for sensor in self.hass.data[DATA_UTILITY][self._parent_meter][
                DATA_TARIFF_SENSORS
            ]:
                sensor.start(new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))
                if self._unit_of_measurement is None:
                    _LOGGER.warning(
                        "Source sensor %s has no unit of measurement. Please %s",
                        self._sensor_source_id,
                        _suggest_report_issue(self.hass, self._sensor_source_id),
                    )

        if (
            adjustment := self.calculate_adjustment(old_state, new_state)
        ) is not None and (self._sensor_net_consumption or adjustment >= 0):
            # If net_consumption is off, the adjustment must be non-negative
            self._state += adjustment  # type: ignore[operator] # self._state will be set to by the start function if it is None, therefore it always has a valid Decimal value at this line

        self._unit_of_measurement = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        self._last_valid_state = new_state_val
        self.async_write_ha_state()

    @callback
    def async_tariff_change(self, event: EventType[EventStateChangedData]) -> None:
        """Handle tariff changes."""
        if (new_state := event.data["new_state"]) is None:
            return

        self._change_status(new_state.state)

    def _change_status(self, tariff: str) -> None:
        if self._tariff == tariff:
            self._collecting = async_track_state_change_event(
                self.hass, [self._sensor_source_id], self.async_reading
            )
        else:
            if self._collecting:
                self._collecting()
            self._collecting = None

        # Reset the last_valid_state during state change because if the last state before the tariff change was invalid,
        # there is no way to know how much "adjustment" counts for which tariff. Therefore, we set the last_valid_state
        # to None and let the fallback mechanism handle the case that the old state was valid
        self._last_valid_state = None

        _LOGGER.debug(
            "%s - %s - source <%s>",
            self._name,
            COLLECTING if self._collecting is not None else PAUSED,
            self._sensor_source_id,
        )

        self.async_write_ha_state()

    async def _async_reset_meter(self, event):
        """Determine cycle - Helper function for larger than daily cycles."""
        if self._cron_pattern is not None:
            self.async_on_remove(
                async_track_point_in_time(
                    self.hass,
                    self._async_reset_meter,
                    croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
                )
            )
        await self.async_reset_meter(self._tariff_entity)

    async def async_reset_meter(self, entity_id):
        """Reset meter."""
        if self._tariff_entity != entity_id:
            return
        _LOGGER.debug("Reset utility meter <%s>", self.entity_id)
        self._last_reset = dt_util.utcnow()
        self._last_period = Decimal(self._state) if self._state else Decimal(0)
        self._state = 0
        self.async_write_ha_state()

    async def async_calibrate(self, value):
        """Calibrate the Utility Meter with a given value."""
        _LOGGER.debug("Calibrate %s = %s type(%s)", self._name, value, type(value))
        self._state = Decimal(str(value))
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if self._cron_pattern is not None:
            self.async_on_remove(
                async_track_point_in_time(
                    self.hass,
                    self._async_reset_meter,
                    croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
                )
            )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RESET_METER, self.async_reset_meter
            )
        )

        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            # new introduced in 2022.04
            self._state = last_sensor_data.native_value
            self._unit_of_measurement = last_sensor_data.native_unit_of_measurement
            self._last_period = last_sensor_data.last_period
            self._last_reset = last_sensor_data.last_reset
            self._last_valid_state = last_sensor_data.last_valid_state
            if last_sensor_data.status == COLLECTING:
                # Null lambda to allow cancelling the collection on tariff change
                self._collecting = lambda: None

        elif state := await self.async_get_last_state():
            # legacy to be removed on 2022.10 (we are keeping this to avoid utility_meter counter losses)
            try:
                self._state = Decimal(state.state)
            except InvalidOperation:
                _LOGGER.error(
                    "Could not restore state <%s>. Resetting utility_meter.%s",
                    state.state,
                    self.name,
                )
            else:
                self._unit_of_measurement = state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT
                )
                self._last_period = (
                    Decimal(state.attributes[ATTR_LAST_PERIOD])
                    if state.attributes.get(ATTR_LAST_PERIOD)
                    and is_number(state.attributes[ATTR_LAST_PERIOD])
                    else Decimal(0)
                )
                self._last_valid_state = (
                    Decimal(state.attributes[ATTR_LAST_VALID_STATE])
                    if state.attributes.get(ATTR_LAST_VALID_STATE)
                    and is_number(state.attributes[ATTR_LAST_VALID_STATE])
                    else None
                )
                self._last_reset = dt_util.as_utc(
                    dt_util.parse_datetime(state.attributes.get(ATTR_LAST_RESET))
                )
                if state.attributes.get(ATTR_STATUS) == COLLECTING:
                    # Null lambda to allow cancelling the collection on tariff change
                    self._collecting = lambda: None

        @callback
        def async_source_tracking(event):
            """Wait for source to be ready, then start meter."""
            if self._tariff_entity is not None:
                _LOGGER.debug(
                    "<%s> tracks utility meter %s", self.name, self._tariff_entity
                )
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, [self._tariff_entity], self.async_tariff_change
                    )
                )

                tariff_entity_state = self.hass.states.get(self._tariff_entity)
                if not tariff_entity_state:
                    # The utility meter is not yet added
                    return

                self._change_status(tariff_entity_state.state)
                return

            _LOGGER.debug(
                "<%s> collecting %s from %s",
                self.name,
                self._unit_of_measurement,
                self._sensor_source_id,
            )
            self._collecting = async_track_state_change_event(
                self.hass, [self._sensor_source_id], self.async_reading
            )

        self.async_on_remove(async_at_started(self.hass, async_source_tracking))

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._collecting:
            self._collecting()
        self._collecting = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_MAP.get(self._unit_of_measurement)

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return (
            SensorStateClass.TOTAL
            if self._sensor_net_consumption
            else SensorStateClass.TOTAL_INCREASING
        )

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_SOURCE_ID: self._sensor_source_id,
            ATTR_STATUS: PAUSED if self._collecting is None else COLLECTING,
            ATTR_LAST_PERIOD: str(self._last_period),
            ATTR_LAST_VALID_STATE: str(self._last_valid_state),
        }
        if self._period is not None:
            state_attr[ATTR_PERIOD] = self._period
        if self._cron_pattern is not None:
            state_attr[ATTR_CRON_PATTERN] = self._cron_pattern
        if self._tariff is not None:
            state_attr[ATTR_TARIFF] = self._tariff
        # last_reset in utility meter was used before last_reset was added for long term
        # statistics in base sensor. base sensor only supports last reset
        # sensors with state_class set to total.
        # To avoid a breaking change we set last_reset directly
        # in extra state attributes.
        if last_reset := self._last_reset:
            state_attr[ATTR_LAST_RESET] = last_reset.isoformat()

        return state_attr

    @property
    def extra_restore_state_data(self) -> UtilitySensorExtraStoredData:
        """Return sensor specific state data to be restored."""
        return UtilitySensorExtraStoredData(
            self.native_value,
            self.native_unit_of_measurement,
            self._last_period,
            self._last_reset,
            self._last_valid_state,
            PAUSED if self._collecting is None else COLLECTING,
        )

    async def async_get_last_sensor_data(self) -> UtilitySensorExtraStoredData | None:
        """Restore Utility Meter Sensor Extra Stored Data."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None

        return UtilitySensorExtraStoredData.from_dict(
            restored_last_extra_data.as_dict()
        )
