"""Support for Netgear LTE modems."""

from typing import Any

from aiohttp.cookiejar import CookieJar
import eternalegypt
from eternalegypt.eternalegypt import SMS

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FROM,
    ATTR_HOST,
    ATTR_MESSAGE,
    ATTR_SMS_ID,
    DATA_HASS_CONFIG,
    DATA_SESSION,
    DOMAIN,
)
from .coordinator import NetgearLTEDataUpdateCoordinator
from .services import async_setup_services

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
type NetgearLTEConfigEntry = ConfigEntry[NetgearLTEDataUpdateCoordinator]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Netgear LTE component."""
    hass.data[DATA_HASS_CONFIG] = config

    return True


async def async_setup_entry(hass: HomeAssistant, entry: NetgearLTEConfigEntry) -> bool:
    """Set up Netgear LTE from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    if not (session := data.get(DATA_SESSION)) or session.closed:
        session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    modem = eternalegypt.Modem(hostname=host, websession=session)

    try:
        await modem.login(password=password)
    except eternalegypt.Error as ex:
        raise ConfigEntryNotReady("Cannot connect/authenticate") from ex

    def fire_sms_event(sms: SMS) -> None:
        """Send an SMS event."""
        data = {
            ATTR_HOST: modem.hostname,
            ATTR_SMS_ID: sms.id,
            ATTR_FROM: sms.sender,
            ATTR_MESSAGE: sms.message,
        }
        hass.bus.async_fire(EVENT_SMS, data)

    await modem.add_sms_listener(fire_sms_event)

    coordinator = NetgearLTEDataUpdateCoordinator(hass, modem)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await async_setup_services(hass, modem)

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_NAME: entry.title, "modem": modem},
        hass.data[DATA_HASS_CONFIG],
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetgearLTEConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        hass.data.pop(DOMAIN, None)
        for service_name in hass.services.async_services()[DOMAIN]:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
