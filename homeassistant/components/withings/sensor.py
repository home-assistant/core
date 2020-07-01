"""Sensors flow for Withings."""
from typing import Any, Callable, Dict, List, Optional, Union

from withings_api.common import UserGetDeviceDevice

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, DEVICE_CLASS_BATTERY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

from . import const
from .common import (
    ApiData,
    BaseWithingsSensor,
    DataManager,
    DeviceSynchronizer,
    async_create_entities,
    async_get_data_manager,
    hass_data_set_value,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    # Start the device synchronizer.
    device_synchronizer = DeviceSynchronizer(
        hass,
        await async_get_data_manager(hass, entry),
        async_add_entities,
        DeviceSensor,
    )
    device_synchronizer.async_start()
    hass_data_set_value(hass, entry, const.DEVICE_SYNCHRONIZER, device_synchronizer)

    # Create the measurement entities.
    entities = await async_create_entities(
        hass, entry, WithingsHealthSensor, SENSOR_DOMAIN,
    )

    async_add_entities(entities, True)


class DeviceSensor(Entity):
    """Provides device data for Withings devices.

    Withings device data cannot be reliably provided from measurement sensor entities
    because all deviced are not represented by Withings data. For example, sleep summary data
    is consolidated from various devices. So in order to ensure we represent all
    Withings devices in HASS, we create a device sensor entity.
    """

    def __init__(self, data_manager: DataManager, device: UserGetDeviceDevice) -> None:
        """Initialize the object."""
        self._data_manager = data_manager
        self._device: UserGetDeviceDevice = device
        self._profile = self._data_manager.profile
        self._name = f"Withings {self._profile} {self._device.model}"
        self._unique_id = f"{const.DOMAIN}_{self._device.deviceid}"
        self._state = 0
        self._update_state()

    def _update_state(self) -> None:
        self._state = 0
        if self._device.battery == "low":
            self._state = 10
        elif self._device.battery == "medium":
            self._state = 50
        elif self._device.battery == "high":
            self._state = 90

    @property
    def should_poll(self) -> bool:
        """Return False to indicate HA should not poll for changes."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "name": f"{self._profile} {self._device.model}",
            "identifiers": {(const.DOMAIN, self._device.deviceid)},
            "manufacturer": "Withings",
            "model": self._device.model,
        }

    @property
    def state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return {ATTR_BATTERY_LEVEL: self._state}

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the entity."""
        return self._state

    @callback
    def _on_poll_data_updated(self) -> None:
        api_data: ApiData = self._data_manager.poll_data_update_coordinator.data
        self._device = next(
            iter(
                device
                for device in api_data.devices
                if device.deviceid == self._device.deviceid
            ),
            self._device,
        )
        self._update_state()

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self.async_on_remove(
            self._data_manager.poll_data_update_coordinator.async_add_listener(
                self._on_poll_data_updated
            )
        )
        self._on_poll_data_updated()


class WithingsHealthSensor(BaseWithingsSensor):
    """Implementation of a Withings sensor."""

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the entity."""
        return self._state_data.value if self._state_data else None
