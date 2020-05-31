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
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_VOLUMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
    SYNO_API,
    UNDO_UPDATE_LISTENER,
)

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
    api = SynoApi(hass, entry)

    await api.async_setup()

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = {
        SYNO_API: api,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

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
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    if unload_ok:
        entry_data = hass.data[DOMAIN][entry.unique_id]
        entry_data[UNDO_UPDATE_LISTENER]()
        await entry_data[SYNO_API].async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistantType, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class SynoApi:
    """Class to interface with Synology DSM API."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry):
        """Initialize the API wrapper class."""
        self._hass = hass
        self._entry = entry

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
            self._entry.data[CONF_HOST],
            self._entry.data[CONF_PORT],
            self._entry.data[CONF_USERNAME],
            self._entry.data[CONF_PASSWORD],
            self._entry.data[CONF_SSL],
            device_token=self._entry.data.get("device_token"),
        )

        await self._hass.async_add_executor_job(self._fetch_device_configuration)
        await self.update()

        self._unsub_dispatcher = async_track_time_interval(
            self._hass,
            self.update,
            timedelta(
                minutes=self._entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
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
