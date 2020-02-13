"""Support for e-connect Elmo alarm system."""
from collections import namedtuple
from datetime import timedelta
import logging

from elmo.api.client import ElmoClient
from elmo.api.exceptions import PermissionDenied
from urllib3.exceptions import HTTPError
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

DOMAIN = "elmo_alarm"

CONF_VENDOR = "vendor"

CONF_STATES = "states"
CONF_ZONES = "zones"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)

SIGNAL_ZONE_CHANGED = "elmo_alarm.zone_changed"
SIGNAL_INPUT_CHANGED = "elmo_alarm.input_changed"
SIGNAL_ARMING_STATE_CHANGED = "elmo_alarm.arming_state_changed"

INPUT_TYPE = "opening"
ZONE_TYPE = "safety"

ZONE_ARMED = 0
ZONE_DISARMED = 1

INPUT_ALERT = 1
INPUT_WAIT = 0

ZoneData = namedtuple("ZoneData", ["zone_id", "zone_name", "state"])
InputData = namedtuple("InputData", ["input_id", "input_name", "state"])


STATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ZONES): vol.All(cv.ensure_list),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_VENDOR): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.time_period, cv.positive_timedelta),
                vol.Required(CONF_STATES): vol.All(cv.ensure_list, [STATE_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the e-connect Elmo Alarm platform."""

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    vendor = conf[CONF_VENDOR]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    states = conf[CONF_STATES]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    _LOGGER.warning("Scan Interval: %s", scan_interval)

    client = ElmoClientWrapper(host, vendor, username, password, states)
    await client.update()

    hass.data[DOMAIN] = client

    hass.async_create_task(
        async_load_platform(
            hass,
            "binary_sensor",
            DOMAIN,
            {"zones": client._zones, "inputs": client._inputs},
            config,
        )
    )

    hass.async_create_task(
        async_load_platform(hass, "alarm_control_panel", DOMAIN, {}, config)
    )

    async def update():
        _LOGGER.debug("Connecting to e-connect to retrieve states")
        await client.update()
        async_dispatcher_send(hass, SIGNAL_ARMING_STATE_CHANGED, client._state)

        for zone in client._zones:
            async_dispatcher_send(hass, SIGNAL_ZONE_CHANGED, zone)

        for inp in client._inputs:
            async_dispatcher_send(hass, SIGNAL_INPUT_CHANGED, inp)

        async_call_later(
            hass,
            scan_interval.total_seconds(),
            lambda _: hass.async_create_task(update()),
        )

    await update()

    return True


class ElmoClientWrapper(ElmoClient):
    """Wrapping the Elmo client class to adapt it to home assistant."""

    def __init__(self, host, vendor, username, password, states_config):
        """Initialize the elmo client wrapper."""

        self._username = username
        self._password = password
        self._states_config = states_config
        self._data = None
        self._states = None
        self._state = None

        ElmoClient.__init__(self, host, vendor)

    async def update(self):
        """Get updates and refresh internal states."""
        try:
            data = self.check()
        except PermissionDenied as e:
            _LOGGER.warning("Invalid session, trying to authenticate %s", e)
            try:
                self.auth(self._username, self._password)
                data = self.check()
            except PermissionDenied as e:
                _LOGGER.warning("Invalid credentials: %s", e)
            except HTTPError as e:
                _LOGGER.warning(
                    "Got HTTP error when authenticating. Check credentials. Code: %s",
                    e.response.status_code,
                )

        if self._data is None:
            await self._configure_states()
        self._data = data
        await self._update_arm_state()
        await self._update_zone_state()
        await self._update_input_state()

    async def _configure_states(self):
        """Initialize the elmo alarm states."""
        state_config = {}
        for state in self._states_config:
            state_config[state[CONF_NAME]] = state[CONF_ZONES]
        self._states = state_config

    async def _update_arm_state(self):
        """Update the elmo alarm states."""
        areas_armed = self._data["areas_armed"]

        if not areas_armed:
            self._state = STATE_ALARM_DISARMED
        else:
            armed_indexes = [x["index"] + 1 for x in areas_armed]

            state = [
                state
                for state, areas in self._states.items()
                if set(areas) == set(armed_indexes)
            ]

            if state:
                state = state[0]
                if state == "arm_away":
                    self._state = STATE_ALARM_ARMED_AWAY
                elif state == "arm_home":
                    self._state = STATE_ALARM_ARMED_HOME
                elif state == "arm_night":
                    self._state = STATE_ALARM_ARMED_NIGHT
                elif state == "arm_custom_bypass":
                    self._state = STATE_ALARM_ARMED_CUSTOM_BYPASS
                else:
                    self._state = None
            else:
                self._state = None

    async def _update_zone_state(self):
        """Update the elmo alarm zone's states."""
        self._zones = [
            ZoneData(zone_id=area["index"], zone_name=area["name"], state=ZONE_ARMED)
            for area in self._data["areas_armed"]
            if area["name"] != "Unknown"
        ]
        self._zones += [
            ZoneData(zone_id=area["index"], zone_name=area["name"], state=ZONE_DISARMED)
            for area in self._data["areas_disarmed"]
            if area["name"] != "Unknown"
        ]

    async def _update_input_state(self):
        """Update the elmo alarm input's states."""
        self._inputs = [
            InputData(input_id=inp["index"], input_name=inp["name"], state=INPUT_ALERT)
            for inp in self._data["inputs_alerted"]
            if inp["name"] != "Unknown"
        ]
        self._inputs += [
            InputData(input_id=inp["index"], input_name=inp["name"], state=INPUT_WAIT)
            for inp in self._data["inputs_wait"]
            if inp["name"] != "Unknown"
        ]
