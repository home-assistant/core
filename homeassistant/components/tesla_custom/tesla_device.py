"""Support for Tesla cars."""
from functools import wraps
import logging
from typing import Any, Optional

from homeassistant.const import ATTR_BATTERY_CHARGING, ATTR_BATTERY_LEVEL
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from teslajsonpy.exceptions import IncompleteCredentials

from .const import DOMAIN, ICONS

_LOGGER = logging.getLogger(__name__)


class TeslaDevice(CoordinatorEntity):
    """Representation of a Tesla device."""

    class Decorators(CoordinatorEntity):
        """Decorators for Tesla Devices."""

        @classmethod
        def check_for_reauth(cls, func):
            """Wrap a Tesla device function to check for need to reauthenticate."""

            @wraps(func)
            async def wrapped(*args, **kwargs):
                result: Any = None
                self_object: Optional[TeslaDevice] = None
                if isinstance(args[0], TeslaDevice):
                    self_object = args[0]
                try:
                    result = await func(*args, **kwargs)
                except IncompleteCredentials:
                    if self_object and self_object.config_entry_id:
                        _LOGGER.debug(
                            "Reauth needed for %s after calling: %s",
                            self_object,
                            func,
                        )
                        await self_object.hass.config_entries.async_reload(
                            self_object.config_entry_id
                        )
                    return None
                return result

            return wrapped

    def __init__(self, tesla_device, coordinator):
        """Initialise the Tesla device."""
        super().__init__(coordinator)
        self.tesla_device = tesla_device
        self._name: str = self.tesla_device.name
        self._unique_id: str = slugify(self.tesla_device.uniq_name)
        self._attributes: str = self.tesla_device.attrs.copy()
        self.config_entry_id: Optional[str] = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self.device_class:
            return None

        return ICONS.get(self.tesla_device.type)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attr = self._attributes
        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.tesla_device.battery_level()
            attr[ATTR_BATTERY_CHARGING] = self.tesla_device.battery_charging()
        return attr

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.tesla_device.id())},
            "name": self.tesla_device.car_name(),
            "manufacturer": "Tesla",
            "model": self.tesla_device.car_type,
            "sw_version": self.tesla_device.car_version,
        }

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(self.coordinator.async_add_listener(self.refresh))
        registry = await async_get_registry(self.hass)
        self.config_entry_id = registry.entities.get(self.entity_id).config_entry_id

    @callback
    def refresh(self) -> None:
        """Refresh the state of the device.

        This assumes the coordinator has updated the controller.
        """
        self.tesla_device.refresh()
        self._attributes = self.tesla_device.attrs.copy()
        self.async_write_ha_state()
