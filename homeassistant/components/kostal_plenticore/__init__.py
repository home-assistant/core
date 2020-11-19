"""The Kostal Plenticore Solar Inverter integration."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
from typing import Any, Dict, Iterable

from kostal.plenticore import PlenticoreApiClient, PlenticoreApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SCOPE_PROCESS_DATA, SCOPE_SETTING
from .sensor import PlenticoreProcessDataSensor

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]

SCAN_INTERVAL = timedelta(seconds=10)


class PlenticoreApi(DataUpdateCoordinator):
    """Data Coordinator for fetching all state of the entities.

    Each entity registers on this coordinator as soon as it is registers in hass. The
    registered entity must provide a scope, module id and data id which is used
    to poll values batched by scope. The values are returned in the data property
    in a nested dict structure ([scope][module id][data id]: value).

    Each entity is checked if the current firmware knows about it before polling.
    If not the entity state is changed to unavailable.

    Entities with scope SCOPE_SETTING are slower much slower polled (5 minutes)
    than SCOPE_PROCESS_DATA.
    """

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, logger: logging.Logger
    ):
        """Create a new Plenticore Update Coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            name="Plenticore",
            update_interval=SCAN_INTERVAL,
            update_method=self._fetch_data,
        )
        self.hass = hass
        self._config = config
        self._login = False
        self._registered_entities = []
        self._available_entities = []
        self._entities_updated = False

        self._client = PlenticoreApiClient(
            async_get_clientsession(hass), host=config[CONF_HOST]
        )

        self._device_info = {
            "identifiers": {(DOMAIN, config[CONF_HOST])},
            "name": config[CONF_NAME],
            "manufacturer": "Kostal",
        }

        # cache for the fetched process and settings data
        self._data = {SCOPE_PROCESS_DATA: {}, SCOPE_SETTING: {}}

        # contains all existing module/data ids after login
        self._existing_data_ids = {SCOPE_PROCESS_DATA: {}, SCOPE_SETTING: {}}

        # last update timestamp of setting values
        self._last_setting_update = None

    async def logout(self) -> None:
        """Log the current logged in user out from the API."""
        if self._login:
            self._login = False
            await self._client.logout()
            _LOGGER.info("Logged out from %s.", self._config[CONF_HOST])

    def register_entity(self, entity: PlenticoreProcessDataSensor) -> None:
        """Register a entity on this instance."""
        self._registered_entities.append(entity)
        self._entities_updated = True

    def unregister_entity(self, entity: PlenticoreProcessDataSensor) -> None:
        """Register a entity on this instance."""
        self._registered_entities = [
            x for x in self._registered_entities if x.unique_id != entity.unique_id
        ]
        self._entities_updated = True

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device info for all plenticore entities."""
        return self._device_info

    async def _update_device_info(self) -> None:
        device_settings = await self._client.get_setting_values(
            module_id="devices:local",
            setting_id=[
                "Properties:SerialNo",
                "Branding:ProductName1",
                "Branding:ProductName2",
                "Properties:VersionIOC",
                "Properties:VersionMC",
            ],
        )

        devices_local = device_settings["devices:local"]

        model = (
            devices_local["Branding:ProductName1"]
            + " "
            + devices_local["Branding:ProductName2"]
        )

        sw_version = (
            f'IOC: {devices_local["Properties:VersionIOC"]}'
            + f' MC: {devices_local["Properties:VersionMC"]}'
        )

        dev_registry = await async_get_registry(self.hass)
        device = dev_registry.async_get_device(
            identifiers={(DOMAIN, self._config[CONF_HOST])}, connections=set()
        )
        if device is not None:
            _LOGGER.info(
                "Update device_info model=%s, sw_version=%s.", model, sw_version
            )
            dev_registry.async_update_device(
                device.id, model=model, sw_version=sw_version
            )

    async def _udpate_existing_data(self) -> None:
        data = await self._client.get_settings()
        self._existing_data_ids[SCOPE_SETTING] = {
            m: set((y.id for y in x)) for m, x in data.items()
        }

        data = await self._client.get_process_data()
        self._existing_data_ids[SCOPE_PROCESS_DATA] = {
            m: set(v) for m, v in data.items()
        }

        self._entities_updated = True

    def _build_request(self, scope: str) -> Dict[str, Iterable[str]]:
        request = defaultdict(list)

        for entity in self._available_entities:
            if entity.scope == scope and entity.enabled:
                request[entity.module_id].append(entity.data_id)

        return request

    def _build_available_entities(self) -> None:
        self._available_entities = []
        for entity in self._registered_entities:
            if (
                entity.scope in self._existing_data_ids
                and entity.module_id in self._existing_data_ids[entity.scope]
                and entity.data_id
                in self._existing_data_ids[entity.scope][entity.module_id]
            ):
                self._available_entities.append(entity)
                entity.available = True
            else:
                entity.available = False
                _LOGGER.info("Entity '%s' is not available on plenticore.", entity.name)

    async def _ensure_login(self) -> None:
        """Ensure that the default user is logged in."""
        if not self._login:
            await self._client.login(self._config[CONF_PASSWORD])
            await self._udpate_existing_data()
            await self._update_device_info()
            _LOGGER.info("Log-in successfully at %s.", self._config[CONF_HOST])
            self._login = True

    async def _fetch_data(self) -> Dict[str, Dict[str, str]]:
        """Fetch process data and setting values from the inverter."""
        if len(self._registered_entities) == 0:
            return {}

        await self._ensure_login()

        if self._entities_updated:
            _LOGGER.debug("Building available entity list.")
            self._build_available_entities()
            self._entities_updated = False

        _process_request = self._build_request(SCOPE_PROCESS_DATA)
        if len(_process_request) > 0:
            _LOGGER.debug("Fetching process data for: %s", _process_request)
            data = await self._client.get_process_data_values(_process_request)
            process_data = {m: {pd.id: pd.value for pd in data[m]} for m in data}
            self._data[SCOPE_PROCESS_DATA].update(process_data)

        # settings does not change that much so we poll this less often
        if self._last_setting_update is None or (
            utcnow() - self._last_setting_update
        ) >= timedelta(seconds=300):
            self._last_setting_update = utcnow()

            _setting_request = self._build_request(SCOPE_SETTING)
            if len(_setting_request) > 0:
                _LOGGER.debug("Fetching setting data for: %s", _setting_request)
                setting_data = await self._client.get_setting_values(_setting_request)
                self._data[SCOPE_SETTING].update(setting_data)

        return self._data

    async def async_write_setting(
        self, module_id: str, setting_id: str, value: str
    ) -> None:
        """Write a new setting value to the inverter."""

        await self._ensure_login()

        _LOGGER.info("Writing '%s' to %s/%s.", value, module_id, setting_id)
        await self._client.set_setting_values(module_id, {setting_id: value})

        self._data[SCOPE_SETTING][module_id][setting_id] = value
        self._last_setting_update = None  # Force update of setting values next time
        self.async_set_updated_data(self._data)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Kostal Plenticore Solar Inverter component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Plenticore Solar Inverter from a config entry."""
    api = PlenticoreApi(hass, entry.data, _LOGGER)

    @callback
    def shutdown(event):
        hass.async_create_task(api.logout())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    hass.data[DOMAIN][entry.entry_id] = api

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        # remove API object
        api = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await api.logout()
        except PlenticoreApiException:
            _LOGGER.exception("Error logging out from inverter.")

    return unload_ok
