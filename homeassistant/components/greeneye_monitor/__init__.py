"""Support for monitoring a GreenEye Monitor energy monitor."""
from __future__ import annotations

import logging
from typing import cast

import greeneye
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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
    DATA_MONITORS,
    DATA_PORTS,
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
    if server_config := config.get(DOMAIN):
        await start_monitoring_server(hass, server_config[CONF_PORT])

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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up greeneye_monitor from a config entry."""
    await start_monitoring_server(hass, config_entry.data[CONF_PORT])

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def start_monitoring_server(hass: HomeAssistant, port: int) -> None:
    """Start the monitoring server on the given port, if it isn't already started."""
    monitors = get_monitors(hass)
    ports: set[int] = hass.data[DOMAIN].setdefault(DATA_PORTS, set())
    if port not in ports:
        await monitors.start_server(port)
        ports.add(port)


def get_monitors(hass: HomeAssistant) -> greeneye.Monitors:
    """Get the Monitors object, creating it if necessary."""
    if DOMAIN not in hass.data:
        monitors = greeneye.Monitors()
        hass.data[DOMAIN] = {
            DATA_MONITORS: monitors,
        }

        async def close_monitors(event: Event) -> None:
            """Close the Monitors object."""
            await monitors.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_monitors)

    return cast(greeneye.Monitors, hass.data[DOMAIN][DATA_MONITORS])
