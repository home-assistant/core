"""The Synology DSM component."""
from datetime import timedelta

from synology_dsm import SynologyDSM
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DISKS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_VOLUMES, DEFAULT_DSM_VERSION, DEFAULT_NAME, DEFAULT_SSL, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_API_VERSION, default=DEFAULT_DSM_VERSION): cv.positive_int,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DISKS): cv.ensure_list,
        vol.Optional(CONF_VOLUMES): cv.ensure_list,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CONFIG_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup(hass, config):
    """Set up Synology DSM sensors from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for dsm_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=dsm_conf,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Synology DSM sensors."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    unit = hass.config.units.temperature_unit
    use_ssl = entry.data[CONF_SSL]
    api_version = entry.data.get(CONF_API_VERSION, DEFAULT_DSM_VERSION)

    api = SynoApi(hass, host, port, username, password, unit, use_ssl, api_version)

    await api.async_setup()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = api

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Synology DSM sensors."""
    api = hass.data[DOMAIN][entry.unique_id]
    await api.async_unload()
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")


class SynoApi:
    """Class to interface with Synology DSM API."""

    def __init__(
        self,
        hass: HomeAssistantType,
        host: str,
        port: int,
        username: str,
        password: str,
        temp_unit: str,
        use_ssl: bool,
        api_version: int,
    ):
        """Initialize the API wrapper class."""
        self._hass = hass
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._api_version = api_version
        self.temp_unit = temp_unit

        self._dsm: SynologyDSM = None
        self.information: SynoDSMInformation = None
        self.utilisation: SynoCoreUtilization = None
        self.storage: SynoStorage = None

        self._unsub_dispatcher = None

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per Synology DSM entry to signal updates in sensors."""
        return f"{DOMAIN}-{self.information.serial}-sensor-update"

    async def async_setup(self):
        """Start interacting with the NAS."""
        self._dsm = SynologyDSM(
            self._host,
            self._port,
            self._username,
            self._password,
            self._use_ssl,
            dsm_version=self._api_version,
        )
        self.information = self._dsm.information
        self.utilisation = self._dsm.utilisation
        self.storage = self._dsm.storage

        await self.update()

        self._unsub_dispatcher = async_track_time_interval(
            self._hass, self.update, SCAN_INTERVAL
        )

    async def async_unload(self):
        """Stop interacting with the NAS and prepare for removal from hass."""
        self._unsub_dispatcher()

    async def update(self, now=None):
        """Update function for updating API information."""
        await self._hass.async_add_executor_job(self._dsm.update)
        async_dispatcher_send(self._hass, self.signal_sensor_update)
