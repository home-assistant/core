"""The Synology DSM component."""
import asyncio
from datetime import timedelta
import logging
from typing import Dict

from synology_dsm import SynologyDSM
from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.dsm.network import SynoDSMNetwork
from synology_dsm.api.storage.storage import SynoStorage
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_DISKS,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CONF_VOLUMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
    ENTITY_CLASS,
    ENTITY_ENABLE,
    ENTITY_ICON,
    ENTITY_NAME,
    ENTITY_UNIT,
    PLATFORMS,
    STORAGE_DISK_BINARY_SENSORS,
    STORAGE_DISK_SENSORS,
    STORAGE_VOL_SENSORS,
    SYNO_API,
    TEMP_SENSORS_KEYS,
    UNDO_UPDATE_LISTENER,
    UTILISATION_SENSORS,
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

ATTRIBUTION = "Data provided by Synology"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up Synology DSM sensors from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for dsm_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=dsm_conf,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Synology DSM sensors."""
    api = SynoApi(hass, entry)

    # Migrate old unique_id
    @callback
    def _async_migrator(entity_entry: entity_registry.RegistryEntry):
        """Migrate away from ID using label."""
        # Reject if new unique_id
        if "SYNO." in entity_entry.unique_id:
            return None

        entries = {
            **STORAGE_DISK_BINARY_SENSORS,
            **STORAGE_DISK_SENSORS,
            **STORAGE_VOL_SENSORS,
            **UTILISATION_SENSORS,
        }
        infos = entity_entry.unique_id.split("_")
        serial = infos.pop(0)
        label = infos.pop(0)
        device_id = "_".join(infos)

        # Removed entity
        if (
            "Type" in entity_entry.unique_id
            or "Device" in entity_entry.unique_id
            or "Name" in entity_entry.unique_id
        ):
            return None

        entity_type = None
        for entity_key, entity_attrs in entries.items():
            if (
                device_id
                and entity_attrs[ENTITY_NAME] == "Status"
                and "Status" in entity_entry.unique_id
                and "(Smart)" not in entity_entry.unique_id
            ):
                if "sd" in device_id and "disk" in entity_key:
                    entity_type = entity_key
                    continue
                if "volume" in device_id and "volume" in entity_key:
                    entity_type = entity_key
                    continue

            if entity_attrs[ENTITY_NAME] == label:
                entity_type = entity_key

        new_unique_id = "_".join([serial, entity_type])
        if device_id:
            new_unique_id += f"_{device_id}"

        _LOGGER.info(
            "Migrating unique_id from [%s] to [%s]",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await entity_registry.async_migrate_entries(hass, entry.entry_id, _async_migrator)

    # Continue setup
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

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Synology DSM sensors."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

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

        # DSM APIs
        self.dsm: SynologyDSM = None
        self.information: SynoDSMInformation = None
        self.network: SynoDSMNetwork = None
        self.security: SynoCoreSecurity = None
        self.storage: SynoStorage = None
        self.utilisation: SynoCoreUtilization = None

        # Should we fetch them
        self._fetching_entities = {}
        self._with_security = True
        self._with_storage = True
        self._with_utilisation = True

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

        self._async_setup_api_requests()

        await self._hass.async_add_executor_job(self._fetch_device_configuration)
        await self.async_update()

        self._unsub_dispatcher = async_track_time_interval(
            self._hass,
            self.async_update,
            timedelta(
                minutes=self._entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

    @callback
    def subscribe(self, api_key, unique_id):
        """Subscribe an entity from API fetches."""
        if api_key not in self._fetching_entities:
            self._fetching_entities[api_key] = set()
        self._fetching_entities[api_key].add(unique_id)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            self._fetching_entities[api_key].remove(unique_id)

        return unsubscribe

    @callback
    def _async_setup_api_requests(self):
        """Determine if we should fetch each API, if one entity needs it."""
        # Entities not added yet, fetch all
        if not self._fetching_entities:
            return

        # Determine if we should fetch an API
        self._with_security = bool(
            self._fetching_entities.get(SynoCoreSecurity.API_KEY)
        )
        self._with_storage = bool(self._fetching_entities.get(SynoStorage.API_KEY))
        self._with_utilisation = bool(
            self._fetching_entities.get(SynoCoreUtilization.API_KEY)
        )

        # Reset not used API
        if not self._with_security:
            self.dsm.reset(self.security)
            self.security = None

        if not self._with_storage:
            self.dsm.reset(self.storage)
            self.storage = None

        if not self._with_utilisation:
            self.dsm.reset(self.utilisation)
            self.utilisation = None

    def _fetch_device_configuration(self):
        """Fetch initial device config."""
        self.information = self.dsm.information
        self.information.update()
        self.network = self.dsm.network
        self.network.update()

        if self._with_security:
            self.security = self.dsm.security

        if self._with_storage:
            self.storage = self.dsm.storage

        if self._with_utilisation:
            self.utilisation = self.dsm.utilisation

    async def async_unload(self):
        """Stop interacting with the NAS and prepare for removal from hass."""
        self._unsub_dispatcher()

    async def async_update(self, now=None):
        """Update function for updating API information."""
        self._async_setup_api_requests()
        await self._hass.async_add_executor_job(self.dsm.update)
        async_dispatcher_send(self._hass, self.signal_sensor_update)


class SynologyDSMEntity(Entity):
    """Representation of a Synology NAS entry."""

    def __init__(
        self,
        api: SynoApi,
        entity_type: str,
        entity_info: Dict[str, str],
    ):
        """Initialize the Synology DSM entity."""
        self._api = api
        self._api_key = entity_type.split(":")[0]
        self.entity_type = entity_type.split(":")[-1]
        self._name = f"{api.network.hostname} {entity_info[ENTITY_NAME]}"
        self._class = entity_info[ENTITY_CLASS]
        self._enable_default = entity_info[ENTITY_ENABLE]
        self._icon = entity_info[ENTITY_ICON]
        self._unit = entity_info[ENTITY_UNIT]
        self._unique_id = f"{self._api.information.serial}_{entity_type}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        if self.entity_type in TEMP_SENSORS_KEYS:
            return self.hass.config.units.temperature_unit
        return self._unit

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return self._class

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.information.serial)},
            "name": "Synology NAS",
            "manufacturer": "Synology",
            "model": self._api.information.model,
            "sw_version": self._api.information.version_string,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enable_default

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_update(self):
        """Only used by the generic entity update service."""
        if not self.enabled:
            return

        await self._api.async_update()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._api.signal_sensor_update, self.async_write_ha_state
            )
        )

        self.async_on_remove(self._api.subscribe(self._api_key, self.unique_id))


class SynologyDSMDeviceEntity(SynologyDSMEntity):
    """Representation of a Synology NAS disk or volume entry."""

    def __init__(
        self,
        api: SynoApi,
        entity_type: str,
        entity_info: Dict[str, str],
        device_id: str = None,
    ):
        """Initialize the Synology DSM disk or volume entity."""
        super().__init__(api, entity_type, entity_info)
        self._device_id = device_id
        self._device_name = None
        self._device_manufacturer = None
        self._device_model = None
        self._device_firmware = None
        self._device_type = None

        if "volume" in entity_type:
            volume = self._api.storage.get_volume(self._device_id)
            # Volume does not have a name
            self._device_name = volume["id"].replace("_", " ").capitalize()
            self._device_manufacturer = "Synology"
            self._device_model = self._api.information.model
            self._device_firmware = self._api.information.version_string
            self._device_type = (
                volume["device_type"]
                .replace("_", " ")
                .replace("raid", "RAID")
                .replace("shr", "SHR")
            )
        elif "disk" in entity_type:
            disk = self._api.storage.get_disk(self._device_id)
            self._device_name = disk["name"]
            self._device_manufacturer = disk["vendor"]
            self._device_model = disk["model"].strip()
            self._device_firmware = disk["firm"]
            self._device_type = disk["diskType"]
        self._name = f"{self._api.network.hostname} {self._device_name} {entity_info[ENTITY_NAME]}"
        self._unique_id += f"_{self._device_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.storage)

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.information.serial, self._device_id)},
            "name": f"Synology NAS ({self._device_name} - {self._device_type})",
            "manufacturer": self._device_manufacturer,
            "model": self._device_model,
            "sw_version": self._device_firmware,
            "via_device": (DOMAIN, self._api.information.serial),
        }
