"""The NIU integration."""
from datetime import timedelta
import logging

from niu import NiuAPIException, NiuCloud

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, NIU_COMPONENTS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up NIU component."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up NIU as config entry."""

    config = entry.data
    username = entry.title
    token = config[CONF_TOKEN]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    try:
        account = NiuCloud(username=username, token=token)
        token = await account.connect()

    except NiuAPIException as ex:
        _LOGGER.error("NIU API Error: %s", ex)
        return False

    async def async_update_data():
        """Fetch data from NIU."""
        await account.update_vehicles()
        return account.get_vehicles()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NIU Update",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "account": account,
    }

    hass.config_entries.async_update_entry(entry, data={**config, CONF_TOKEN: token})

    for component in NIU_COMPONENTS:
        _LOGGER.debug("Loading %s", component)

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class NiuVehicle(CoordinatorEntity, Entity):
    """Represents a NIU vehicle."""

    def __init__(self, vehicle_id, device_class, coordinator):
        """Initialize the class."""
        super().__init__(coordinator)
        self._id = vehicle_id
        self._device_class = device_class

    @property
    def _vehicle(self):
        return self.coordinator.data[self._id]

    @property
    def name(self):
        """Return the vehicle's name."""
        return self._vehicle.name

    @property
    def unique_id(self):
        """Return the vehicle's unique id."""
        return self._id

    @property
    def device_class(self):
        """Return the sensor's class."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._vehicle.name,
            "manufacturer": "NIU",
            "model": self._vehicle.model,
            "sw_version": self._vehicle.firmware_version,
        }

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self._vehicle.soc(),
            ATTR_BATTERY_CHARGING: self._vehicle.is_charging,
        }
