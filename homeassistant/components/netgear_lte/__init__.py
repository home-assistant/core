"""Support for Netgear LTE modems."""
from datetime import timedelta

from aiohttp.cookiejar import CookieJar
import attr
import eternalegypt
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FROM,
    ATTR_HOST,
    ATTR_MESSAGE,
    ATTR_SMS_ID,
    CONF_BINARY_SENSOR,
    CONF_NOTIFY,
    CONF_SENSOR,
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


NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
        vol.Optional(CONF_RECIPIENT, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["usage"]): vol.All(
            cv.ensure_list, [vol.In(ALL_SENSORS)]
        )
    }
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["mobile_connected"]): vol.All(
            cv.ensure_list, [vol.In(ALL_BINARY_SENSORS)]
        )
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

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NOTIFY,
    Platform.SENSOR,
]


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

    if lte_config := config.get(DOMAIN):
        hass.async_create_task(import_yaml(hass, lte_config))

    return True


async def import_yaml(hass: HomeAssistant, lte_config: ConfigType) -> None:
    """Import yaml if we can connect. Create appropriate issue registry entries."""
    for entry in lte_config:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
        )
        if result.get("reason") == "cannot_connect":
            async_create_issue(
                hass,
                DOMAIN,
                "import_failure",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="import_failure",
            )
        else:
            async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Netgear LTE",
                },
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netgear LTE from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    if DOMAIN not in hass.data:
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

    _legacy_task(hass, entry)

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
        hass.data.pop(DOMAIN)

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


def _legacy_task(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create notify service and add a repair issue when appropriate."""
    # Discovery can happen up to 2 times for notify depending on existing yaml config
    # One for the name of the config entry, allows the user to customize the name
    # One for each notify described in the yaml config which goes away with config flow
    # One for the default if the user never specified one
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_HOST: entry.data[CONF_HOST], CONF_NAME: entry.title},
            hass.data[DATA_HASS_CONFIG],
        )
    )
    if not (lte_configs := hass.data[DATA_HASS_CONFIG].get(DOMAIN, [])):
        return
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_notify",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_notify",
        translation_placeholders={
            "name": f"{Platform.NOTIFY}.{entry.title.lower().replace(' ', '_')}"
        },
    )

    for lte_config in lte_configs:
        if lte_config[CONF_HOST] == entry.data[CONF_HOST]:
            if not lte_config[CONF_NOTIFY]:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        Platform.NOTIFY,
                        DOMAIN,
                        {CONF_HOST: entry.data[CONF_HOST], CONF_NAME: DOMAIN},
                        hass.data[DATA_HASS_CONFIG],
                    )
                )
                break
            for notify_conf in lte_config[CONF_NOTIFY]:
                discovery_info = {
                    CONF_HOST: lte_config[CONF_HOST],
                    CONF_NAME: notify_conf.get(CONF_NAME),
                    CONF_NOTIFY: notify_conf,
                }
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        Platform.NOTIFY,
                        DOMAIN,
                        discovery_info,
                        hass.data[DATA_HASS_CONFIG],
                    )
                )
            break
