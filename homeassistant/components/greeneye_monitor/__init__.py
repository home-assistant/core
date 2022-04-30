"""Support for monitoring a GreenEye Monitor energy monitor."""
from __future__ import annotations

import logging

import greeneye
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_TEMPERATURE_UNIT,
    EVENT_HOMEASSISTANT_STOP,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHANNELS,
    CONF_COUNTED_QUANTITY,
    CONF_COUNTED_QUANTITY_PER_PULSE,
    CONF_MONITORS,
    CONF_NET_METERING,
    CONF_NUMBER,
    CONF_PULSE_COUNTERS,
    CONF_SERIAL_NUMBER,
    CONF_TEMPERATURE_SENSORS,
    CONF_TIME_UNIT,
    CONF_VOLTAGE_SENSORS,
    DATA_GREENEYE_MONITOR,
    DOMAIN,
    TEMPERATURE_UNIT_CELSIUS,
)

_LOGGER = logging.getLogger(__name__)

TEMPERATURE_SENSOR_SCHEMA = vol.Schema(
    {vol.Required(CONF_NUMBER): vol.Range(1, 8), vol.Required(CONF_NAME): cv.string}
)

TEMPERATURE_SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
        vol.Required(CONF_SENSORS): vol.All(
            cv.ensure_list, [TEMPERATURE_SENSOR_SCHEMA]
        ),
    }
)

VOLTAGE_SENSOR_SCHEMA = vol.Schema(
    {vol.Required(CONF_NUMBER): vol.Range(1, 48), vol.Required(CONF_NAME): cv.string}
)

VOLTAGE_SENSORS_SCHEMA = vol.All(cv.ensure_list, [VOLTAGE_SENSOR_SCHEMA])

PULSE_COUNTER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NUMBER): vol.Range(1, 4),
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_COUNTED_QUANTITY): cv.string,
        vol.Optional(CONF_COUNTED_QUANTITY_PER_PULSE, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_TIME_UNIT, default=TIME_SECONDS): vol.Any(
            TIME_SECONDS, TIME_MINUTES, TIME_HOURS
        ),
    }
)

PULSE_COUNTERS_SCHEMA = vol.All(cv.ensure_list, [PULSE_COUNTER_SCHEMA])

CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NUMBER): vol.Range(1, 48),
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_NET_METERING, default=False): cv.boolean,
    }
)

CHANNELS_SCHEMA = vol.All(cv.ensure_list, [CHANNEL_SCHEMA])

MONITOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): vol.All(
            cv.string,
            vol.Length(
                min=8,
                max=8,
                msg="GEM serial number must be specified as an 8-character "
                "string (including leading zeroes).",
            ),
            vol.Coerce(int),
        ),
        vol.Optional(CONF_CHANNELS, default=[]): CHANNELS_SCHEMA,
        vol.Optional(
            CONF_TEMPERATURE_SENSORS,
            default={CONF_TEMPERATURE_UNIT: TEMPERATURE_UNIT_CELSIUS, CONF_SENSORS: []},
        ): TEMPERATURE_SENSORS_SCHEMA,
        vol.Optional(CONF_PULSE_COUNTERS, default=[]): PULSE_COUNTERS_SCHEMA,
        vol.Optional(CONF_VOLTAGE_SENSORS, default=[]): VOLTAGE_SENSORS_SCHEMA,
    }
)

MONITORS_SCHEMA = vol.All(cv.ensure_list, [MONITOR_SCHEMA])

COMPONENT_SCHEMA = vol.Schema(
    {vol.Required(CONF_PORT): cv.port, vol.Required(CONF_MONITORS): MONITORS_SCHEMA}
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: COMPONENT_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GreenEye Monitor component."""
    monitors = greeneye.Monitors()
    hass.data[DATA_GREENEYE_MONITOR] = monitors

    server_config = config[DOMAIN]
    await monitors.start_server(server_config[CONF_PORT])

    async def close_monitors(event: Event) -> None:
        """Close the Monitors object."""
        await monitors.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_monitors)

    num_sensors = 0
    for monitor_config in config[DOMAIN][CONF_MONITORS]:
        num_sensors += len(monitor_config[CONF_CHANNELS])
        num_sensors += len(monitor_config[CONF_PULSE_COUNTERS])
        num_sensors += len(monitor_config[CONF_TEMPERATURE_SENSORS][CONF_SENSORS])
        num_sensors += len(monitor_config[CONF_VOLTAGE_SENSORS])

    if num_sensors == 0:
        _LOGGER.error(
            "Configuration must specify at least one "
            "channel, voltage, pulse counter or temperature sensor"
        )
        return False

    hass.async_create_task(
        async_load_platform(hass, Platform.SENSOR, DOMAIN, config[DOMAIN], config)
    )

    return True
