"""Support for SimpliSafe alarm control panels."""
import logging
import re

from simplipy.sensor import SensorTypes
from simplipy.system import SystemStates

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    FORMAT_TEXT,
    AlarmControlPanel,
)
from homeassistant.const import (
    CONF_CODE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.dt import utc_from_timestamp

from .const import DATA_CLIENT, DOMAIN, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)

ATTR_ALARM_ACTIVE = "alarm_active"
ATTR_BATTERY_BACKUP_POWER_LEVEL = "battery_backup_power_level"
ATTR_GSM_STRENGTH = "gsm_strength"
ATTR_LAST_EVENT_INFO = "last_event_info"
ATTR_LAST_EVENT_SENSOR_NAME = "last_event_sensor_name"
ATTR_LAST_EVENT_SENSOR_TYPE = "last_event_sensor_type"
ATTR_LAST_EVENT_TIMESTAMP = "last_event_timestamp"
ATTR_LAST_EVENT_TYPE = "last_event_type"
ATTR_RF_JAMMING = "rf_jamming"
ATTR_SYSTEM_ID = "system_id"
ATTR_WALL_POWER_LEVEL = "wall_power_level"
ATTR_WIFI_STRENGTH = "wifi_strength"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a SimpliSafe alarm control panel based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a SimpliSafe alarm control panel based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            SimpliSafeAlarm(simplisafe, system, entry.data.get(CONF_CODE))
            for system in simplisafe.systems.values()
        ],
        True,
    )


class SimpliSafeAlarm(AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe, system, code):
        """Initialize the SimpliSafe alarm."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_SYSTEM_ID: system.system_id}
        self._changed_by = None
        self._code = code
        self._simplisafe = simplisafe
        self._state = None
        self._system = system

        # Some properties only exist for V2 or V3 systems:
        for prop in (
            ATTR_BATTERY_BACKUP_POWER_LEVEL,
            ATTR_GSM_STRENGTH,
            ATTR_RF_JAMMING,
            ATTR_WALL_POWER_LEVEL,
            ATTR_WIFI_STRENGTH,
        ):
            if hasattr(system, prop):
                self._attrs[prop] = getattr(system, prop)

    @property
    def changed_by(self):
        """Return info about who changed the alarm last."""
        return self._changed_by

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if not self._code:
            return None
        if isinstance(self._code, str) and re.search("^\\d+$", self._code):
            return FORMAT_NUMBER
        return FORMAT_TEXT

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._system.system_id)},
            "manufacturer": "SimpliSafe",
            "model": self._system.version,
            # The name should become more dynamic once we deduce a way to
            # get various other sensors from SimpliSafe in a reliable manner:
            "name": "Keypad",
            "via_device": (DOMAIN, self._system.serial),
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self):
        """Return the name of the entity."""
        return self._system.address

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._system.system_id

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, "disarming"):
            return

        await self._system.set_off()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, "arming home"):
            return

        await self._system.set_home()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, "arming away"):
            return

        await self._system.set_away()

    async def async_update(self):
        """Update alarm status."""
        event_data = self._simplisafe.last_event_data[self._system.system_id]

        if event_data["pinName"]:
            self._changed_by = event_data["pinName"]

        if self._system.state == SystemStates.error:
            return

        if self._system.state == SystemStates.off:
            self._state = STATE_ALARM_DISARMED
        elif self._system.state in (SystemStates.home, SystemStates.home_count):
            self._state = STATE_ALARM_ARMED_HOME
        elif self._system.state in (
            SystemStates.away,
            SystemStates.away_count,
            SystemStates.exit_delay,
        ):
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = None

        last_event = self._simplisafe.last_event_data[self._system.system_id]
        self._attrs.update(
            {
                ATTR_ALARM_ACTIVE: self._system.alarm_going_off,
                ATTR_LAST_EVENT_INFO: last_event["info"],
                ATTR_LAST_EVENT_SENSOR_NAME: last_event["sensorName"],
                ATTR_LAST_EVENT_SENSOR_TYPE: SensorTypes(last_event["sensorType"]).name,
                ATTR_LAST_EVENT_TIMESTAMP: utc_from_timestamp(
                    last_event["eventTimestamp"]
                ),
                ATTR_LAST_EVENT_TYPE: last_event["eventType"],
            }
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
