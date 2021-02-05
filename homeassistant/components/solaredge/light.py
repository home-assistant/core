"""Support for SolarEdge HA API."""
from datetime import timedelta
import logging

from requests.exceptions import ConnectTimeout, HTTPError
import solaredgeha

from homeassistant.components.light import LightEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_SITE_ID, DOMAIN, HA_UPDATE_DELAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add an solarEdge entry."""

    if not (CONF_USERNAME in entry.data and CONF_PASSWORD in entry.data):
        _LOGGER.error("SolarEdge HA required configuration not present")
        return

    # Add the lights to hass
    api = solaredgeha.SolaredgeHa(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    # Check if api can be reached and site is active
    try:
        response = await hass.async_add_executor_job(
            api.get_devices, entry.data[CONF_SITE_ID]
        )
        if response["status"] != "PASSED":
            _LOGGER.error("SolarEdge HA site is not active")
            return
        _LOGGER.debug("Credentials correct and site is active")
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    service = SolarEdgeHaService(
        hass, entry.title, api, entry.data[CONF_SITE_ID], async_add_entities
    )
    service.async_setup()
    await service.coordinator.async_refresh()


class SolarEdgeHaService:
    """Get and update the HA device data."""

    def __init__(self, hass, platform_name, api, site_id, async_add_entities):
        """Initialize the data object."""
        _LOGGER.debug("Creating SolarEdgeHaService")

        self._update_interval = HA_UPDATE_DELAY

        self.hass = hass
        self.platform_name = platform_name
        self.api = api
        self.site_id = site_id
        self.async_add_entities = async_add_entities

        self.devices = {}

        self.coordinator = None

    @callback
    def async_setup(self):
        """Coordinator creation."""
        _LOGGER.debug("Creating SolarEdgeHaService.coordinator")
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=str(self),
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    def update_interval(self):
        """Update interval."""
        _LOGGER.debug("SolarEdgeHaService.update_interval")
        return self._update_interval

    def update(self):
        """Update the devices from SolarEdge HA API."""
        _LOGGER.debug("SolarEdgeHaService.update")

        try:
            response = self.api.get_devices(self.site_id)
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        refresh_rate = timedelta(seconds=response["updateRefreshRate"])
        if self._update_interval != refresh_rate:
            _LOGGER.debug("Update interval updated to %s", str(refresh_rate))
            self._update_interval = refresh_rate
            self.coordinator.update_interval = self._update_interval

        for device in response["devices"]:
            if device["type"] == "ON_OFF":
                key = device["reporterId"]
                if key not in self.devices:
                    _LOGGER.debug("SolarEdge HA adding new light %s", key)
                    self.devices[key] = device
                    self.async_add_entities(
                        [SolarEdgeLight(self.platform_name, key, self)]
                    )
                else:
                    _LOGGER.debug("SolarEdge HA updating light %s", key)
                    self.devices[key] = device

    async def async_update_data(self):
        """Update data."""
        _LOGGER.debug("SolarEdgeHaService.async_update_data")
        await self.hass.async_add_executor_job(self.update)


class SolarEdgeLight(CoordinatorEntity, LightEntity):
    """Representation of a SolarEdge HA light."""

    def __init__(self, platform_name, light_key, data_service):
        """Initialize the light."""
        super().__init__(data_service.coordinator)
        self._platform_name = platform_name
        self._light_key = light_key
        self._data_service = data_service

    @property
    def device_state(self):
        """Return the state of the light."""
        return self._data_service.devices[self._light_key]

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self.device_state["manufacturer"],
            "model": self.device_state["model"],
            "sw_version": self.device_state["swVersion"],
        }

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light_key

    @property
    def name(self):
        """Return the display name of this light."""
        return self.device_state["name"]

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device_state["status"]["level"] > 0

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._data_service.api.activate_device(self._light_key, 100)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._data_service.api.activate_device(self._light_key, 0)
