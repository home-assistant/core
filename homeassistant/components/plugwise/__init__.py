"""Plugwise platform for Home Assistant Core."""

import asyncio
from datetime import timedelta
import logging
from typing import Dict

from Plugwise_Smile.Smile import Smile
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, THERMOSTAT_ICON

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

SENSOR_PLATFORMS = ["sensor"]
ALL_PLATFORMS = ["climate", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Plugwise platform."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise Smiles from a config entry."""
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=entry.data["host"], password=entry.data["password"], websession=websession
    )

    try:
        connected = await api.connect()

        if not connected:
            _LOGGER.error("Unable to connect to Smile")
            raise ConfigEntryNotReady

    except Smile.InvalidAuthentication:
        _LOGGER.error("Invalid Smile ID")
        return False

    except Smile.PlugwiseError:
        _LOGGER.error("Error while communicating to device")
        raise ConfigEntryNotReady

    except asyncio.TimeoutError:
        _LOGGER.error("Timeout while connecting to Smile")
        raise ConfigEntryNotReady

    if api.smile_type == "power":
        update_interval = timedelta(seconds=10)
    else:
        update_interval = timedelta(seconds=60)

    async def async_update_data():
        """Update data via API endpoint."""
        try:
            async with async_timeout.timeout(10):
                await api.full_update_device()
                return True
        except Smile.XMLDataMissingError:
            raise UpdateFailed("Smile update failed")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Smile",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    api.get_all_devices()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, api.gateway_id)},
        manufacturer="Plugwise",
        name=entry.title,
        model=f"Smile {api.smile_name}",
        sw_version=api.smile_version[0],
    )

    platforms = ALL_PLATFORMS

    single_master_thermostat = api.single_master_thermostat()
    if single_master_thermostat is None:
        platforms = SENSOR_PLATFORMS

    for component in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in ALL_PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SmileGateway(Entity):
    """Represent Smile Gateway."""

    def __init__(self, api, coordinator):
        """Initialise the gateway."""
        self._api = api
        self._coordinator = coordinator
        self._unique_id = None
        self._name = None
        self._icon = None
        self._dev_id = None
        self._model = None
        self._gateway_id = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def name(self):
        """Return the name of the entity, if any."""
        if not self._name:
            return None
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if not self._icon:
            return THERMOSTAT_ICON
        return self._icon

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""

        device_information = {
            "identifiers": {(DOMAIN, self._dev_id)},
            "name": self._name,
            "manufacturer": "Plugwise",
        }

        if self._model is not None:
            device_information["model"] = self._model.replace("_", " ").title()

        if self._dev_id != self._gateway_id:
            device_information["via_device"] = (DOMAIN, self._gateway_id)

        return device_information

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(self._coordinator.async_add_listener(self._process_data))

    def _process_data(self):
        """Interpret and process API data."""
        raise NotImplementedError

    async def async_update(self):
        """Update the entity."""
        await self._coordinator.async_request_refresh()


class SmileSensor(SmileGateway):
    """Represent Smile Sensors."""

    def __init__(self, api, coordinator):
        """Initialise the sensor."""
        super().__init__(api, coordinator)

        self._dev_class = None
        self._state = None
        self._unit_of_measurement = None

    @property
    def device_class(self):
        """Device class of this entity."""
        if not self._dev_class:
            return None
        return self._dev_class

    @property
    def state(self):
        """Device class of this entity."""
        if not self._state:
            return None
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if not self._unit_of_measurement:
            return None
        return self._unit_of_measurement
