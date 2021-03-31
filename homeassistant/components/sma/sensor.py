"""SMA Solar Webconnect interface."""
from datetime import timedelta
import logging

import pysma
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

CONF_CUSTOM = "custom"
CONF_FACTOR = "factor"
CONF_GROUP = "group"
CONF_KEY = "key"
CONF_UNIT = "unit"

GROUPS = ["user", "installer"]


def _check_sensor_schema(conf):
    """Check sensors and attributes are valid."""
    try:
        valid = [s.name for s in pysma.Sensors()]
    except (ImportError, AttributeError):
        return conf

    customs = list(conf[CONF_CUSTOM])

    for sensor in conf[CONF_SENSORS]:
        if sensor in customs:
            _LOGGER.warning(
                "All custom sensors will be added automatically, no need to include them in sensors: %s",
                sensor,
            )
        elif sensor not in valid:
            raise vol.Invalid(f"{sensor} does not exist")
    return conf


CUSTOM_SCHEMA = vol.Any(
    {
        vol.Required(CONF_KEY): vol.All(cv.string, vol.Length(min=13, max=15)),
        vol.Required(CONF_UNIT): cv.string,
        vol.Optional(CONF_FACTOR, default=1): vol.Coerce(float),
        vol.Optional(CONF_PATH): vol.All(cv.ensure_list, [cv.string]),
    }
)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_SSL, default=False): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_GROUP, default=GROUPS[0]): vol.In(GROUPS),
            vol.Optional(CONF_SENSORS, default=[]): vol.Any(
                cv.schema_with_slug_keys(cv.ensure_list),  # will be deprecated
                vol.All(cv.ensure_list, [str]),
            ),
            vol.Optional(CONF_CUSTOM, default={}): cv.schema_with_slug_keys(
                CUSTOM_SCHEMA
            ),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    _check_sensor_schema,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up SMA WebConnect sensor."""
    # Check config again during load - dependency available
    config = _check_sensor_schema(config)

    # Init all default sensors
    sensor_def = pysma.Sensors()

    # Sensor from the custom config
    sensor_def.add(
        [
            pysma.Sensor(o[CONF_KEY], n, o[CONF_UNIT], o[CONF_FACTOR], o.get(CONF_PATH))
            for n, o in config[CONF_CUSTOM].items()
        ]
    )

    # Use all sensors by default
    config_sensors = config[CONF_SENSORS]
    hass_sensors = []
    used_sensors = []

    if isinstance(config_sensors, dict):  # will be remove from 0.99
        if not config_sensors:  # Use all sensors by default
            config_sensors = {s.name: [] for s in sensor_def}

        # Prepare all Home Assistant sensor entities
        for name, attr in config_sensors.items():
            sub_sensors = [sensor_def[s] for s in attr]
            hass_sensors.append(SMAsensor(sensor_def[name], sub_sensors))
            used_sensors.append(name)
            used_sensors.extend(attr)

    if isinstance(config_sensors, list):
        if not config_sensors:  # Use all sensors by default
            config_sensors = [s.name for s in sensor_def]
        used_sensors = list(set(config_sensors + list(config[CONF_CUSTOM])))
        for sensor in used_sensors:
            hass_sensors.append(SMAsensor(sensor_def[sensor], []))

    used_sensors = [sensor_def[s] for s in set(used_sensors)]
    async_add_entities(hass_sensors)

    # Init the SMA interface
    session = async_get_clientsession(hass, verify_ssl=config[CONF_VERIFY_SSL])
    grp = config[CONF_GROUP]

    protocol = "https" if config[CONF_SSL] else "http"
    url = f"{protocol}://{config[CONF_HOST]}"

    sma = pysma.SMA(session, url, config[CONF_PASSWORD], group=grp)

    # Ensure we logout on shutdown
    async def async_close_session(event):
        """Close the session."""
        await sma.close_session()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_close_session)

    backoff = 0
    backoff_step = 0

    async def async_sma(event):
        """Update all the SMA sensors."""
        nonlocal backoff, backoff_step
        if backoff > 1:
            backoff -= 1
            return

        values = await sma.read(used_sensors)
        if not values:
            try:
                backoff = [1, 1, 1, 6, 30][backoff_step]
                backoff_step += 1
            except IndexError:
                backoff = 60
            return
        backoff_step = 0

        for sensor in hass_sensors:
            sensor.async_update_values()

    interval = config.get(CONF_SCAN_INTERVAL) or timedelta(seconds=5)
    async_track_time_interval(hass, async_sma, interval)


class SMAsensor(Entity):
    """Representation of a SMA sensor."""

    def __init__(self, pysma_sensor, sub_sensors):
        """Initialize the sensor."""
        self._sensor = pysma_sensor
        self._sub_sensors = sub_sensors  # Can be remove from 0.99

        self._attr = {s.name: "" for s in sub_sensors}
        self._state = self._sensor.value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._sensor.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor.unit

    @property
    def device_state_attributes(self):  # Can be remove from 0.99
        """Return the state attributes of the sensor."""
        return self._attr

    @property
    def poll(self):
        """SMA sensors are updated & don't poll."""
        return False

    @callback
    def async_update_values(self):
        """Update this sensor."""
        update = False

        for sens in self._sub_sensors:  # Can be remove from 0.99
            newval = f"{sens.value} {sens.unit}"
            if self._attr[sens.name] != newval:
                update = True
                self._attr[sens.name] = newval

        if self._sensor.value != self._state:
            update = True
            self._state = self._sensor.value

        if update:
            self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"sma-{self._sensor.key}-{self._sensor.name}"
