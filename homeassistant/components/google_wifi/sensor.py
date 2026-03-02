"""Support for retrieving status info from Google Wifi/OnHub routers."""
from __future__ import annotations

import logging
from datetime import timedelta

import async_timeout
import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SENSOR_TYPES, ATTR_UPTIME, ATTR_LAST_RESTART, ATTR_NEW_VERSION, ATTR_STATUS, ATTR_LOCAL_IP, ATTR_MODEL, ATTR_GROUP_ROLE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Google Wifi sensor from a config entry."""
    # Retrieve the data we stored in __init__.py
    data = hass.data[DOMAIN][entry.entry_id]
    ip_address = data["ip_address"]
    device_name = data["name"]

    # Create the coordinator to manage data updates
    coordinator = GoogleWifiUpdateCoordinator(hass, ip_address)
    
    # Fetch initial data so we don't have empty sensors on startup
    await coordinator.async_config_entry_first_refresh()

    # Add all sensors defined in SENSOR_TYPES
    async_add_entities(
        GoogleWifiSensor(coordinator, description, device_name)
        for description in SENSOR_TYPES
    )


class GoogleWifiUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Google Wifi API."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the coordinator."""
        self.host = host
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch data from the router via HTTP."""
        url = f"http://{self.host}/api/v1/status"
        try:
            # We use hass.async_add_executor_job because 'requests' is synchronous
            async with async_timeout.timeout(10):
                response = await self.hass.async_add_executor_job(
                    requests.get, url
                )
            return response.json()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class GoogleWifiSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Google Wifi sensor."""

    def __init__(
        self,
        coordinator: GoogleWifiUpdateCoordinator,
        description,
        device_name
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_name = device_name
        # Create a unique ID so the user can rename/customize this in the UI
        self._attr_unique_id = f"{coordinator.host}_{description.key}"
        self._attr_name = f"Google Wifi {description.key.replace('_', ' ').title()}"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach sensors to a device in HomeAssistant"""
        # Pull the version and model name from the coordinator's data cache
        version = None
        if self.coordinator.data:
            try:
                version = self.coordinator.data["software"]["softwareVersion"]
                model_name = self.coordinator.data["system"]["modelId"]
            except KeyError:
                version = None
                model_name = "Onhub/Wifi"

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=self.device_name,
            manufacturer="Google",
            model=model_name,
            sw_version=version,
            configuration_url=f"http://{self.coordinator.host}/api/v1/status",
        )

    @property
    def native_value(self):
        """Return the state of the sensor based on the coordinator data."""
        if not self.coordinator.data:
            return None

        raw_data = self.coordinator.data
        desc = self.entity_description
        
        try:
            val = raw_data[desc.primary_key][desc.sensor_key]
            
            # Formatting Logic
            if desc.key == ATTR_NEW_VERSION and val == "0.0.0.0":
                return "Latest"
            if desc.key == ATTR_UPTIME:
                return round(val / (3600 * 24), 2)
            if desc.key == ATTR_LAST_RESTART:
                last_restart = dt_util.now() - timedelta(seconds=val)
                return last_restart.strftime("%Y-%m-%d %H:%M:%S")
            if desc.key == ATTR_STATUS:
                return "Online" if val else "Offline"
            if desc.key == ATTR_LOCAL_IP and not raw_data["wan"]["online"]:
                return None
                
            return val
        except KeyError:
            return None
