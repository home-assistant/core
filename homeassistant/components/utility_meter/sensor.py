"""Utility meter from sensors providing raw data."""
from datetime import date, timedelta
from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_VALUE,
    BIMONTHLY,
    CONF_METER,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFF,
    CONF_TARIFF_ENTITY,
    DAILY,
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

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"
ATTR_STATUS = "status"
ATTR_PERIOD = "meter_period"
ATTR_LAST_PERIOD = "last_period"
ATTR_LAST_RESET = "last_reset"
ATTR_TARIFF = "tariff"

ICON = "mdi:counter"

PRECISION = 3
PAUSED = "paused"
COLLECTING = "collecting"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the utility meter sensor."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    meters = []
    for conf in discovery_info:
        meter = conf[CONF_METER]
        conf_meter_source = hass.data[DATA_UTILITY][meter][CONF_SOURCE_SENSOR]
        conf_meter_type = hass.data[DATA_UTILITY][meter].get(CONF_METER_TYPE)
        conf_meter_offset = hass.data[DATA_UTILITY][meter][CONF_METER_OFFSET]
        conf_meter_net_consumption = hass.data[DATA_UTILITY][meter][
            CONF_METER_NET_CONSUMPTION
        ]
        conf_meter_tariff_entity = hass.data[DATA_UTILITY][meter].get(
            CONF_TARIFF_ENTITY
        )

        meters.append(
            UtilityMeterSensor(
                conf_meter_source,
                conf.get(CONF_NAME),
                conf_meter_type,
                conf_meter_offset,
                conf_meter_net_consumption,
                conf.get(CONF_TARIFF),
                conf_meter_tariff_entity,
            )
        )

    async_add_entities(meters)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_CALIBRATE_METER,
        {vol.Required(ATTR_VALUE): vol.Coerce(Decimal)},
        "async_calibrate",
    )


class UtilityMeterSensor(RestoreEntity):
    """Representation of an utility meter sensor."""

    def __init__(
        self,
        source_entity,
        name,
        meter_type,
        meter_offset,
        net_consumption,
        tariff=None,
        tariff_entity=None,
    ):
        """Initialize the Utility Meter sensor."""
        self._sensor_source_id = source_entity
        self._state = 0
        self._last_period = 0
        self._last_reset = dt_util.now()
        self._collecting = None
        if name:
            self._name = name
        else:
            self._name = f"{source_entity} meter"
        self._unit_of_measurement = None
        self._period = meter_type
        self._period_offset = meter_offset
        self._sensor_net_consumption = net_consumption
        self._tariff = tariff
        self._tariff_entity = tariff_entity

    @callback
    def async_reading(self, event):
        """Handle the sensor state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if (
            old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            return

        self._unit_of_measurement = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            diff = Decimal(new_state.state) - Decimal(old_state.state)

            if (not self._sensor_net_consumption) and diff < 0:
                # Source sensor just rolled over for unknown reasons,
                return
            self._state += diff

        except ValueError as err:
            _LOGGER.warning("While processing state changes: %s", err)
        except DecimalException as err:
            _LOGGER.warning(
                "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
            )
        self.async_write_ha_state()

    @callback
    def async_tariff_change(self, event):
        """Handle tariff changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
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
        now = dt_util.now().date()
        if (
            self._period == WEEKLY
            and now != now - timedelta(days=now.weekday()) + self._period_offset
        ):
            return
        if (
            self._period == MONTHLY
            and now != date(now.year, now.month, 1) + self._period_offset
        ):
            return
        if (
            self._period == BIMONTHLY
            and now
            != date(now.year, (((now.month - 1) // 2) * 2 + 1), 1) + self._period_offset
        ):
            return
        if (
            self._period == QUARTERLY
            and now
            != date(now.year, (((now.month - 1) // 3) * 3 + 1), 1) + self._period_offset
        ):
            return
        if self._period == YEARLY and now != date(now.year, 1, 1) + self._period_offset:
            return
        await self.async_reset_meter(self._tariff_entity)

    async def async_reset_meter(self, entity_id):
        """Reset meter."""
        if self._tariff_entity != entity_id:
            return
        _LOGGER.debug("Reset utility meter <%s>", self.entity_id)
        self._last_reset = dt_util.now()
        self._last_period = str(self._state)
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

        if self._period == QUARTER_HOURLY:
            for quarter in range(4):
                async_track_time_change(
                    self.hass,
                    self._async_reset_meter,
                    minute=(quarter * 15)
                    + self._period_offset.seconds % (15 * 60) // 60,
                    second=self._period_offset.seconds % 60,
                )
        elif self._period == HOURLY:
            async_track_time_change(
                self.hass,
                self._async_reset_meter,
                minute=self._period_offset.seconds // 60,
                second=self._period_offset.seconds % 60,
            )
        elif self._period in [DAILY, WEEKLY, MONTHLY, BIMONTHLY, QUARTERLY, YEARLY]:
            async_track_time_change(
                self.hass,
                self._async_reset_meter,
                hour=self._period_offset.seconds // 3600,
                minute=self._period_offset.seconds % 3600 // 60,
                second=self._period_offset.seconds % 3600 % 60,
            )

        async_dispatcher_connect(self.hass, SIGNAL_RESET_METER, self.async_reset_meter)

        state = await self.async_get_last_state()
        if state:
            self._state = Decimal(state.state)
            self._unit_of_measurement = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            self._last_period = state.attributes.get(ATTR_LAST_PERIOD)
            self._last_reset = dt_util.parse_datetime(
                state.attributes.get(ATTR_LAST_RESET)
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

            _LOGGER.debug("<%s> collecting from %s", self.name, self._sensor_source_id)
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
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_SOURCE_ID: self._sensor_source_id,
            ATTR_STATUS: PAUSED if self._collecting is None else COLLECTING,
            ATTR_LAST_PERIOD: self._last_period,
            ATTR_LAST_RESET: self._last_reset,
        }
        if self._period is not None:
            state_attr[ATTR_PERIOD] = self._period
        if self._tariff is not None:
            state_attr[ATTR_TARIFF] = self._tariff
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON
