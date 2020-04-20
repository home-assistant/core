"""Support for Netgear LTE modems."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import attr
import eternalegypt
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from . import sensor_types

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
DISPATCHER_NETGEAR_LTE = "netgear_lte_update"

DOMAIN = "netgear_lte"
DATA_KEY = "netgear_lte"

EVENT_SMS = "netgear_lte_sms"

SERVICE_DELETE_SMS = "delete_sms"
SERVICE_SET_OPTION = "set_option"
SERVICE_CONNECT_LTE = "connect_lte"
SERVICE_DISCONNECT_LTE = "disconnect_lte"

ATTR_HOST = "host"
ATTR_SMS_ID = "sms_id"
ATTR_FROM = "from"
ATTR_MESSAGE = "message"
ATTR_FAILOVER = "failover"
ATTR_AUTOCONNECT = "autoconnect"

FAILOVER_MODES = ["auto", "wire", "mobile"]
AUTOCONNECT_MODES = ["never", "home", "always"]


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
                        vol.Optional(NOTIFY_DOMAIN, default={}): vol.All(
                            cv.ensure_list, [NOTIFY_SCHEMA]
                        ),
                        vol.Optional(SENSOR_DOMAIN, default={}): SENSOR_SCHEMA,
                        vol.Optional(
                            BINARY_SENSOR_DOMAIN, default={}
                        ): BINARY_SENSOR_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

DELETE_SMS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HOST): cv.string,
        vol.Required(ATTR_SMS_ID): vol.All(cv.ensure_list, [cv.positive_int]),
    }
)

SET_OPTION_SCHEMA = vol.Schema(
    vol.All(
        cv.has_at_least_one_key(ATTR_FAILOVER, ATTR_AUTOCONNECT),
        {
            vol.Optional(ATTR_HOST): cv.string,
            vol.Optional(ATTR_FAILOVER): vol.In(FAILOVER_MODES),
            vol.Optional(ATTR_AUTOCONNECT): vol.In(AUTOCONNECT_MODES),
        },
    )
)

CONNECT_LTE_SCHEMA = vol.Schema({vol.Optional(ATTR_HOST): cv.string})

DISCONNECT_LTE_SCHEMA = vol.Schema({vol.Optional(ATTR_HOST): cv.string})


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
                _LOGGER.warning("Connected to %s", self.host)
                self.connected = True
        except eternalegypt.Error:
            if self.connected:
                _LOGGER.warning("Lost connection to %s", self.host)
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


async def async_setup(hass, config):
    """Set up Netgear LTE component."""
    if DATA_KEY not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        hass.data[DATA_KEY] = LTEData(websession)

        async def service_handler(service):
            """Apply a service."""
            host = service.data.get(ATTR_HOST)
            conf = {CONF_HOST: host}
            modem_data = hass.data[DATA_KEY].get_modem_data(conf)

            if not modem_data:
                _LOGGER.error("%s: host %s unavailable", service.service, host)
                return

            if service.service == SERVICE_DELETE_SMS:
                for sms_id in service.data[ATTR_SMS_ID]:
                    await modem_data.modem.delete_sms(sms_id)
            elif service.service == SERVICE_SET_OPTION:
                failover = service.data.get(ATTR_FAILOVER)
                if failover:
                    await modem_data.modem.set_failover_mode(failover)

                autoconnect = service.data.get(ATTR_AUTOCONNECT)
                if autoconnect:
                    await modem_data.modem.set_autoconnect_mode(autoconnect)
            elif service.service == SERVICE_CONNECT_LTE:
                await modem_data.modem.connect_lte()
            elif service.service == SERVICE_DISCONNECT_LTE:
                await modem_data.modem.disconnect_lte()

        service_schemas = {
            SERVICE_DELETE_SMS: DELETE_SMS_SCHEMA,
            SERVICE_SET_OPTION: SET_OPTION_SCHEMA,
            SERVICE_CONNECT_LTE: CONNECT_LTE_SCHEMA,
            SERVICE_DISCONNECT_LTE: DISCONNECT_LTE_SCHEMA,
        }

        for service, schema in service_schemas.items():
            hass.services.async_register(
                DOMAIN, service, service_handler, schema=schema
            )

    netgear_lte_config = config[DOMAIN]

    # Set up each modem
    tasks = [_setup_lte(hass, lte_conf) for lte_conf in netgear_lte_config]
    await asyncio.wait(tasks)

    # Load platforms for each modem
    for lte_conf in netgear_lte_config:
        # Notify
        for notify_conf in lte_conf[NOTIFY_DOMAIN]:
            discovery_info = {
                CONF_HOST: lte_conf[CONF_HOST],
                CONF_NAME: notify_conf.get(CONF_NAME),
                NOTIFY_DOMAIN: notify_conf,
            }
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, NOTIFY_DOMAIN, DOMAIN, discovery_info, config
                )
            )

        # Sensor
        sensor_conf = lte_conf.get(SENSOR_DOMAIN)
        discovery_info = {CONF_HOST: lte_conf[CONF_HOST], SENSOR_DOMAIN: sensor_conf}
        hass.async_create_task(
            discovery.async_load_platform(
                hass, SENSOR_DOMAIN, DOMAIN, discovery_info, config
            )
        )

        # Binary Sensor
        binary_sensor_conf = lte_conf.get(BINARY_SENSOR_DOMAIN)
        discovery_info = {
            CONF_HOST: lte_conf[CONF_HOST],
            BINARY_SENSOR_DOMAIN: binary_sensor_conf,
        }
        hass.async_create_task(
            discovery.async_load_platform(
                hass, BINARY_SENSOR_DOMAIN, DOMAIN, discovery_info, config
            )
        )

    return True


async def _setup_lte(hass, lte_config):
    """Set up a Netgear LTE modem."""

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DATA_KEY].websession
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
    hass.data[DATA_KEY].modem_data[modem_data.host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        await modem_data.modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    async def _update(now):
        """Periodic update."""
        await modem_data.async_update()

    async_track_time_interval(hass, _update, SCAN_INTERVAL)


async def _retry_login(hass, modem_data, password):
    """Sleep and retry setup."""

    _LOGGER.warning("Could not connect to %s. Will keep trying", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
        except eternalegypt.Error:
            delay = min(2 * delay, 300)


@attr.s
class LTEEntity(Entity):
    """Base LTE entity."""

    modem_data = attr.ib()
    sensor_type = attr.ib()

    _unique_id = attr.ib(init=False)

    @_unique_id.default
    def _init_unique_id(self):
        """Register unique_id while we know data is valid."""
        return f"{self.sensor_type}_{self.modem_data.data.serial_number}"

    async def async_added_to_hass(self):
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_NETGEAR_LTE, self.async_write_ha_state
            )
        )

    async def async_update(self):
        """Force update of state."""
        await self.modem_data.async_update()

    @property
    def should_poll(self):
        """Return that the sensor should not be polled."""
        return False

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self.modem_data.data is not None

    @property
    def unique_id(self):
        """Return a unique ID like 'usage_5TG365AB0078V'."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Netgear LTE {self.sensor_type}"
