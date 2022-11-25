"""The PurpleAir integration."""
from __future__ import annotations

import asyncio

from aiopurpleair.models.sensors import SensorModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import CONF_SENSOR_INDEX, DOMAIN
from .coordinator import PurpleAirDataUpdateCoordinator

COORDINATOR_LOCK = asyncio.Lock()

MAP_URL_BASE = "https://map.purpleair.com/1/mAQI/a10/p604800/cC0"

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PurpleAir from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]

    # Although the common pattern for integrations is to have a coordinator for every
    # config entry, we create a coordinator per API key to consolidate API calls
    # (the PurpleAir API can handle multiple sensor indices in a single call). To ensure
    # config entries don't encounter a race condition, we lock the configuration of the
    # coordinator:
    async with COORDINATOR_LOCK:
        if coordinator := hass.data[DOMAIN].get(api_key):
            coordinator.async_track_sensor_index(entry.data[CONF_SENSOR_INDEX])
        else:
            coordinator = PurpleAirDataUpdateCoordinator(hass, api_key)

        try:
            if hass.state != CoreState.running:
                # If HASS is starting up, we utilize a debouncer (so that multiple
                # PurpleAir config entries don't hammer the API upon startup); once one
                # call succeeds, all existing config entries that use this API key will
                # have fresh data:
                await coordinator.async_request_refresh()
            else:
                # If HASS is already running, we assume this is a newly-added config
                # entry, which should request data right away:
                await coordinator.async_refresh()
        except UpdateFailed as err:
            raise ConfigEntryNotReady() from err
        else:
            hass.data[DOMAIN].setdefault(api_key, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api_key = entry.data[CONF_API_KEY]
        coordinator: PurpleAirDataUpdateCoordinator = hass.data[DOMAIN][api_key]
        sensor_index = entry.data[CONF_SENSOR_INDEX]

        async with COORDINATOR_LOCK:
            # If this is the last sensor index being tracked by this coordinator, we
            # remove it; we use the lock here in the case of a reauth flow, which will
            # unload all config entries using this coordinator at the same time:
            still_tracking = coordinator.async_untrack_sensor_index(sensor_index)
            if not still_tracking:
                hass.data[DOMAIN].pop(api_key)

    return unload_ok


class PurpleAirEntity(CoordinatorEntity[PurpleAirDataUpdateCoordinator]):
    """Define a base PurpleAir entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PurpleAirDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._sensor_index = entry.data[CONF_SENSOR_INDEX]

        self._attr_device_info = DeviceInfo(
            configuration_url=f"{MAP_URL_BASE}?select={self._sensor_index}",
            hw_version=self.sensor_data.hardware,
            identifiers={(DOMAIN, str(self._sensor_index))},
            manufacturer="PurpleAir, Inc.",
            model=self.sensor_data.model,
            name=self.sensor_data.name,
            sw_version=self.sensor_data.firmware_version,
        )
        self._attr_extra_state_attributes = {
            ATTR_LATITUDE: self.sensor_data.latitude,
            ATTR_LONGITUDE: self.sensor_data.longitude,
        }

    @property
    def sensor_data(self) -> SensorModel:
        """Define a property to get this entity's SensorModel object."""
        return self.coordinator.data.data[self._sensor_index]
