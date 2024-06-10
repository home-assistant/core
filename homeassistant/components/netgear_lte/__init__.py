"""Support for Netgear LTE modems."""

from datetime import timedelta

from aiohttp.cookiejar import CookieJar
import attr
import eternalegypt

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FROM,
    ATTR_HOST,
    ATTR_MESSAGE,
    ATTR_SMS_ID,
    DATA_HASS_CONFIG,
    DISPATCHER_NETGEAR_LTE,
    DOMAIN,
    LOGGER,
)
from .services import async_setup_services

SCAN_INTERVAL = timedelta(seconds=10)

EVENT_SMS = "netgear_lte_sms"

ALL_SENSORS = [
    "sms",
    "sms_total",
    "usage",
    "radio_quality",
    "rx_level",
    "tx_level",
    "upstream",
    "connection_text",
    "connection_type",
    "current_ps_service_type",
    "register_network_display",
    "current_band",
    "cell_id",
]

ALL_BINARY_SENSORS = [
    "roaming",
    "wire_connected",
    "mobile_connected",
]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NOTIFY,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
    modem_data: dict[str, ModemData] = attr.ib(init=False, factory=dict)

    def get_modem_data(self, config):
        """Get modem_data for the host in config."""
        if config[CONF_HOST] is not None:
            return self.modem_data.get(config[CONF_HOST])
        if len(self.modem_data) != 1:
            return None
        return next(iter(self.modem_data.values()))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Netgear LTE component."""
    hass.data[DATA_HASS_CONFIG] = config

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netgear LTE from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    if not (data := hass.data.get(DOMAIN)) or data.websession.closed:
        websession = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))

        hass.data[DOMAIN] = LTEData(websession)

    modem = eternalegypt.Modem(hostname=host, websession=hass.data[DOMAIN].websession)
    modem_data = ModemData(hass, host, modem)

    await _login(hass, modem_data, password)

    async def _update(now):
        """Periodic update."""
        await modem_data.async_update()

    update_unsub = async_track_time_interval(hass, _update, SCAN_INTERVAL)

    async def cleanup(event: Event | None = None) -> None:
        """Clean up resources."""
        update_unsub()
        await modem.logout()
        if DOMAIN in hass.data:
            del hass.data[DOMAIN].modem_data[modem_data.host]

    entry.async_on_unload(cleanup)
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup))

    await async_setup_services(hass)

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_HOST: entry.data[CONF_HOST], CONF_NAME: entry.title},
        hass.data[DATA_HASS_CONFIG],
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        hass.data.pop(DOMAIN, None)

    return unload_ok


async def _login(hass: HomeAssistant, modem_data: ModemData, password: str) -> None:
    """Log in and complete setup."""
    try:
        await modem_data.modem.login(password=password)
    except eternalegypt.Error as ex:
        raise ConfigEntryNotReady("Cannot connect/authenticate") from ex

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
