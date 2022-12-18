"""The PurpleAir integration."""
from __future__ import annotations

from aiopurpleair.models.sensors import SensorModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import async_remove_sensor_by_device_id
from .const import CONF_LAST_UPDATE_SENSOR_ADD, DOMAIN
from .coordinator import PurpleAirDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PurpleAir from a config entry."""
    coordinator = PurpleAirDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_handle_entry_update))

    return True


async def async_handle_entry_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    if entry.options.get(CONF_LAST_UPDATE_SENSOR_ADD) is True:
        # If the last options update was to add a sensor, we reload the config entry:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    new_entry_options = async_remove_sensor_by_device_id(
        hass,
        config_entry,
        device_entry.id,
        # remove_device is set to False because in this instance, the device has
        # already been removed:
        remove_device=False,
    )
    return hass.config_entries.async_update_entry(
        config_entry, options=new_entry_options
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PurpleAirEntity(CoordinatorEntity[PurpleAirDataUpdateCoordinator]):
    """Define a base PurpleAir entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PurpleAirDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_index: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._sensor_index = sensor_index

        self._attr_device_info = DeviceInfo(
            configuration_url=self.coordinator.async_get_map_url(sensor_index),
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
