"""The Synology DSM component."""
from datetime import timedelta

from synology_dsm import SynologyDSM
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_VOLUMES, DEFAULT_SSL, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
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
    device_token = entry.data.get("device_token")

    api = SynoApi(hass, host, port, username, password, unit, use_ssl, device_token)

    await api.async_setup()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = api

    # For SSDP compat
    if not entry.data.get(CONF_MAC):
        network = await hass.async_add_executor_job(getattr, api.dsm, "network")
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MAC: network.macs}
        )

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
        device_token: str,
    ):
        """Initialize the API wrapper class."""
        self._hass = hass
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._device_token = device_token
        self.temp_unit = temp_unit

        self.dsm: SynologyDSM = None
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
        self.dsm = SynologyDSM(
            self._host,
            self._port,
            self._username,
            self._password,
            self._use_ssl,
            device_token=self._device_token,
        )

        await self._hass.async_add_executor_job(self._fetch_device_configuration)
        await self.update()

        self._unsub_dispatcher = async_track_time_interval(
            self._hass, self.update, SCAN_INTERVAL
        )

    def _fetch_device_configuration(self):
        """Fetch initial device config."""
        self.information = self.dsm.information
        self.utilisation = self.dsm.utilisation
        self.storage = self.dsm.storage

    async def async_unload(self):
        """Stop interacting with the NAS and prepare for removal from hass."""
        self._unsub_dispatcher()

    async def update(self, now=None):
        """Update function for updating API information."""
        await self._hass.async_add_executor_job(self.dsm.update)
        async_dispatcher_send(self._hass, self.signal_sensor_update)
