"""Support for Netgear LTE modems."""
import asyncio
from datetime import timedelta

import aiohttp
import attr
import eternalegypt
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from . import sensor_types
from .const import (
    ATTR_FROM,
    ATTR_HOST,
    ATTR_MESSAGE,
    ATTR_SMS_ID,
    CONF_BINARY_SENSOR,
    CONF_NOTIFY,
    CONF_SENSOR,
    DISPATCHER_NETGEAR_LTE,
    DOMAIN,
    LOGGER,
)
from .services import async_setup_services

SCAN_INTERVAL = timedelta(seconds=10)

EVENT_SMS = "netgear_lte_sms"


NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
        vol.Optional(CONF_RECIPIENT, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=sensor_types.DEFAULT_SENSORS
        ): vol.All(cv.ensure_list, [vol.In(sensor_types.ALL_SENSORS)])
    }
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=sensor_types.DEFAULT_BINARY_SENSORS
        ): vol.All(cv.ensure_list, [vol.In(sensor_types.ALL_BINARY_SENSORS)])
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_NOTIFY, default={}): vol.All(
                            cv.ensure_list, [NOTIFY_SCHEMA]
                        ),
                        vol.Optional(CONF_SENSOR, default={}): SENSOR_SCHEMA,
                        vol.Optional(
                            CONF_BINARY_SENSOR, default={}
                        ): BINARY_SENSOR_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@attr.s
class ModemData:
    """Class for modem state."""

    hass = attr.ib()
    host = attr.ib()
    modem = attr.ib()

    data = attr.ib(init=False, default=None)
    connected = attr.ib(init=False, default=True)

    async def async_update(self):
        """Call the API to update the data."""

        try:
            self.data = await self.modem.information()
            if not self.connected:
                LOGGER.warning("Connected to %s", self.host)
                self.connected = True
        except eternalegypt.Error:
            if self.connected:
                LOGGER.warning("Lost connection to %s", self.host)
                self.connected = False
            self.data = None

        async_dispatcher_send(self.hass, DISPATCHER_NETGEAR_LTE)


@attr.s
class LTEData:
    """Shared state."""

    websession = attr.ib()
    modem_data = attr.ib(init=False, factory=dict)

    def get_modem_data(self, config):
        """Get modem_data for the host in config."""
        if config[CONF_HOST] is not None:
            return self.modem_data.get(config[CONF_HOST])
        if len(self.modem_data) != 1:
            return None
        return next(iter(self.modem_data.values()))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Netgear LTE component."""
    if DOMAIN not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        hass.data[DOMAIN] = LTEData(websession)

        await async_setup_services(hass)

    netgear_lte_config = config[DOMAIN]

    # Set up each modem
    tasks = [
        hass.async_create_task(_setup_lte(hass, lte_conf))
        for lte_conf in netgear_lte_config
    ]
    await asyncio.wait(tasks)

    # Load platforms for each modem
    for lte_conf in netgear_lte_config:
        # Notify
        for notify_conf in lte_conf[CONF_NOTIFY]:
            discovery_info = {
                CONF_HOST: lte_conf[CONF_HOST],
                CONF_NAME: notify_conf.get(CONF_NAME),
                CONF_NOTIFY: notify_conf,
            }
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, Platform.NOTIFY, DOMAIN, discovery_info, config
                )
            )

        # Sensor
        sensor_conf = lte_conf[CONF_SENSOR]
        discovery_info = {CONF_HOST: lte_conf[CONF_HOST], CONF_SENSOR: sensor_conf}
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.SENSOR, DOMAIN, discovery_info, config
            )
        )

        # Binary Sensor
        binary_sensor_conf = lte_conf[CONF_BINARY_SENSOR]
        discovery_info = {
            CONF_HOST: lte_conf[CONF_HOST],
            CONF_BINARY_SENSOR: binary_sensor_conf,
        }
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.BINARY_SENSOR, DOMAIN, discovery_info, config
            )
        )

    return True


async def _setup_lte(hass, lte_config):
    """Set up a Netgear LTE modem."""

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DOMAIN].websession
    modem = eternalegypt.Modem(hostname=host, websession=websession)

    modem_data = ModemData(hass, host, modem)

    try:
        await _login(hass, modem_data, password)
    except eternalegypt.Error:
        retry_task = hass.loop.create_task(_retry_login(hass, modem_data, password))

        @callback
        def cleanup_retry(event):
            """Clean up retry task resources."""
            if not retry_task.done():
                retry_task.cancel()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_retry)


async def _login(hass, modem_data, password):
    """Log in and complete setup."""
    await modem_data.modem.login(password=password)

    def fire_sms_event(sms):
        """Send an SMS event."""
        data = {
            ATTR_HOST: modem_data.host,
            ATTR_SMS_ID: sms.id,
            ATTR_FROM: sms.sender,
            ATTR_MESSAGE: sms.message,
        }
        hass.bus.async_fire(EVENT_SMS, data)

    await modem_data.modem.add_sms_listener(fire_sms_event)

    await modem_data.async_update()
    hass.data[DOMAIN].modem_data[modem_data.host] = modem_data

    async def _update(now):
        """Periodic update."""
        await modem_data.async_update()

    update_unsub = async_track_time_interval(hass, _update, SCAN_INTERVAL)

    async def cleanup(event):
        """Clean up resources."""
        update_unsub()
        await modem_data.modem.logout()
        del hass.data[DOMAIN].modem_data[modem_data.host]

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)


async def _retry_login(hass, modem_data, password):
    """Sleep and retry setup."""

    LOGGER.warning("Could not connect to %s. Will keep trying", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
        except eternalegypt.Error:
            delay = min(2 * delay, 300)
