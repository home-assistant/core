"""Utility meter from sensors providing raw data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DecimalException, InvalidOperation
import logging

from croniter import croniter
import voluptuous as vol

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import is_number
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
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
ATTR_TARIFF = "tariff"

DEVICE_CLASS_MAP = {
    ENERGY_WATT_HOUR: SensorDeviceClass.ENERGY,
    ENERGY_KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
}

ICON = "mdi:counter"

PRECISION = 3
PAUSED = "paused"
COLLECTING = "collecting"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the utility meter sensor."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    meters = []
    for conf in discovery_info.values():
        meter = conf[CONF_METER]
        conf_meter_source = hass.data[DATA_UTILITY][meter][CONF_SOURCE_SENSOR]
        conf_meter_type = hass.data[DATA_UTILITY][meter].get(CONF_METER_TYPE)
        conf_meter_offset = hass.data[DATA_UTILITY][meter][CONF_METER_OFFSET]
        conf_meter_delta_values = hass.data[DATA_UTILITY][meter][
            CONF_METER_DELTA_VALUES
        ]
        conf_meter_net_consumption = hass.data[DATA_UTILITY][meter][
            CONF_METER_NET_CONSUMPTION
        ]
        conf_meter_tariff_entity = hass.data[DATA_UTILITY][meter].get(
            CONF_TARIFF_ENTITY
        )
        conf_cron_pattern = hass.data[DATA_UTILITY][meter].get(CONF_CRON_PATTERN)
        meter_sensor = UtilityMeterSensor(
            meter,
            conf_meter_source,
            conf.get(CONF_NAME),
            conf_meter_type,
            conf_meter_offset,
            conf_meter_delta_values,
            conf_meter_net_consumption,
            conf.get(CONF_TARIFF),
            conf_meter_tariff_entity,
            conf_cron_pattern,
        )
        meters.append(meter_sensor)

        hass.data[DATA_UTILITY][meter][DATA_TARIFF_SENSORS].append(meter_sensor)

    async_add_entities(meters)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_CALIBRATE_METER,
        {vol.Required(ATTR_VALUE): vol.Coerce(Decimal)},
        "async_calibrate",
    )


class UtilityMeterSensor(RestoreEntity, SensorEntity):
    """Representation of an utility meter sensor."""

    def __init__(
        self,
        parent_meter,
        source_entity,
        name,
        meter_type,
        meter_offset,
        delta_values,
        net_consumption,
        tariff=None,
        tariff_entity=None,
        cron_pattern=None,
    ):
        """Initialize the Utility Meter sensor."""
        self._parent_meter = parent_meter
        self._sensor_source_id = source_entity
        self._state = None
        self._last_period = Decimal(0)
        self._last_reset = dt_util.utcnow()
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
        self._tariff = tariff
        self._tariff_entity = tariff_entity

    def start(self, unit):
        """Initialize unit and state upon source initial update."""
        self._unit_of_measurement = unit
        self._state = 0
        self.async_write_ha_state()

    @callback
    def async_reading(self, event):
        """Handle the sensor state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if self._state is None and new_state.state:
            # First state update initializes the utility_meter sensors
            source_state = self.hass.states.get(self._sensor_source_id)
            for sensor in self.hass.data[DATA_UTILITY][self._parent_meter][
                DATA_TARIFF_SENSORS
            ]:
                sensor.start(source_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))

        if (
            old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            return

        self._unit_of_measurement = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            if self._sensor_delta_values:
                adjustment = Decimal(new_state.state)
            else:
                adjustment = Decimal(new_state.state) - Decimal(old_state.state)

            if (not self._sensor_net_consumption) and adjustment < 0:
                # Source sensor just rolled over for unknown reasons,
                return
            self._state += adjustment

        except DecimalException as err:
            _LOGGER.warning(
                "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
            )
        self.async_write_ha_state()

    @callback
    def async_tariff_change(self, event):
        """Handle tariff changes."""
        if (new_state := event.data.get("new_state")) is None:
            return

        self._change_status(new_state.state)

    def _change_status(self, tariff):
        if self._tariff == tariff:
            self._collecting = async_track_state_change_event(
                self.hass, [self._sensor_source_id], self.async_reading
            )
        else:
            if self._collecting:
                self._collecting()
            self._collecting = None

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
            async_track_point_in_time(
                self.hass,
                self._async_reset_meter,
                croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
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
        _LOGGER.debug("Calibrate %s = %s", self._name, value)
        self._state = value
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        if self._cron_pattern is not None:
            async_track_point_in_time(
                self.hass,
                self._async_reset_meter,
                croniter(self._cron_pattern, dt_util.now()).get_next(datetime),
            )

        async_dispatcher_connect(self.hass, SIGNAL_RESET_METER, self.async_reset_meter)

        if state := await self.async_get_last_state():
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
                self._last_reset = dt_util.as_utc(
                    dt_util.parse_datetime(state.attributes.get(ATTR_LAST_RESET))
                )
                if state.attributes.get(ATTR_STATUS) == COLLECTING:
                    # Fake cancellation function to init the meter in similar state
                    self._collecting = lambda: None

        @callback
        def async_source_tracking(event):
            """Wait for source to be ready, then start meter."""
            if self._tariff_entity is not None:
                _LOGGER.debug(
                    "<%s> tracks utility meter %s", self.name, self._tariff_entity
                )
                async_track_state_change_event(
                    self.hass, [self._tariff_entity], self.async_tariff_change
                )

                tariff_entity_state = self.hass.states.get(self._tariff_entity)
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

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_source_tracking
        )

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
        return DEVICE_CLASS_MAP.get(self.unit_of_measurement)

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
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_SOURCE_ID: self._sensor_source_id,
            ATTR_STATUS: PAUSED if self._collecting is None else COLLECTING,
            ATTR_LAST_PERIOD: str(self._last_period),
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
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON
