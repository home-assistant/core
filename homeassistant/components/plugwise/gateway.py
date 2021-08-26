"""Plugwise platform for Home Assistant Core."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout
from plugwise.exceptions import (
    InvalidAuthentication,
    PlugwiseException,
    XMLDataMissingError,
)
from plugwise.smile import Smile
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API,
    CLIMATE_DOMAIN,
    COORDINATOR,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    GATEWAY,
    GATEWAY_PLATFORMS,
    PW_TYPE,
    SENSOR_PLATFORMS,
    SERVICE_DELETE,
    UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry_gw(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise Smiles from a config entry."""
    websession = async_get_clientsession(hass, verify_ssl=False)

    api = Smile(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=30,
        websession=websession,
    )

    try:
        connected = await api.connect()
        if not connected:
            _LOGGER.error("Unable to connect to the Smile/Stretch")
            raise ConfigEntryNotReady
    except InvalidAuthentication:
        _LOGGER.error("Invalid username or Smile ID")
        return False
    except PlugwiseException as err:
        _LOGGER.error("Error while communicating to the Smile/Stretch")
        raise ConfigEntryNotReady from err
    except asyncio.TimeoutError as err:
        _LOGGER.error("Timeout while connecting to the Smile/Stretch")
        raise ConfigEntryNotReady from err

    # Migrate to a valid unique_id when needed
    if entry.unique_id is None:
        if api.smile_version[0] != "1.8.0":
            hass.config_entries.async_update_entry(entry, unique_id=api.smile_hostname)

    update_interval = timedelta(
        seconds=entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL[api.smile_type]
        )
    )

    async def async_update_gw_data():
        """Update data via API endpoint."""
        _LOGGER.debug("Updating %s", api.smile_name)
        try:
            async with async_timeout.timeout(update_interval.seconds):
                await api.update_gw_devices()
                return True
        except XMLDataMissingError as err:
            raise UpdateFailed("Smile update failed") from err
        except PlugwiseException as err:
            _LOGGER.debug("Updating failed, generic failure for %s", api.smile_name)
            raise UpdateFailed("Smile update failed") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{api.smile_name}",
        update_method=async_update_gw_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    undo_listener = entry.add_update_listener(_update_listener)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        API: api,
        COORDINATOR: coordinator,
        PW_TYPE: GATEWAY,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    api.get_all_devices()

    platforms = GATEWAY_PLATFORMS
    if api.single_master_thermostat() is None:
        platforms = SENSOR_PLATFORMS

    async def delete_notification(self):
        """Service: delete the Plugwise Notification."""
        try:
            deleted = await api.delete_notification()
            _LOGGER.debug("PW Notification deleted: %s", deleted)
        except PlugwiseException:
            _LOGGER.debug(
                "Failed to delete the Plugwise Notification for %s", api.smile_name
            )

    for component in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
        if component == CLIMATE_DOMAIN:
            hass.services.async_register(
                DOMAIN, SERVICE_DELETE, delete_notification, schema=vol.Schema({})
            )

    return True


async def async_unload_entry_gw(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in GATEWAY_PLATFORMS
            )
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL)
    )


class SmileGateway(CoordinatorEntity):
    """Represent Smile Gateway."""

    def __init__(self, api, coordinator, dev_id, name, model, vendor, fw):
        """Initialise the gateway."""
        super().__init__(coordinator)

        self._api = api
        self._coordinator = coordinator
        self._dev_id = dev_id
        self._device_class = None
        self._device_name = name
        self._fw_version = fw
        self._manufacturer = vendor
        self._model = model
        self._name = None
        self._unique_id = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def device_info(self) -> dict[str, any]:
        """Return the device information."""
        device_information = {
            "identifiers": {(DOMAIN, self._dev_id)},
            "name": self._device_name,
            "manufacturer": self._manufacturer,
            "model": self._model,
            "sw_version": self._fw_version,
        }

        if self._dev_id != self._api.gateway_id:
            device_information["via_device"] = (DOMAIN, self._api.gateway_id)
        else:
            device_information["name"] = f"Smile {self._api.smile_name}"

        return device_information

    @property
    def name(self):
        """Return the name of the entity, if any."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._async_process_data()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_process_data)
        )

    @callback
    def _async_process_data(self):
        """Interpret and process API data."""
        raise NotImplementedError
