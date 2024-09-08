"""Home Connect entity base class."""

import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .api import HomeConnectDevice
from .const import DOMAIN, SIGNAL_UPDATE_ENTITIES
from .utils import bsh_key_to_translation_key

_LOGGER = logging.getLogger(__name__)


class HomeConnectEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Description of a Home Connect entity."""


class HomeConnectEntity(Entity):
    """Generic Home Connect entity (base class)."""

    entity_description: HomeConnectEntityDescription
    device: HomeConnectDevice
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, device: HomeConnectDevice, desc: HomeConnectEntityDescription
    ) -> None:
        """Initialize the entity."""
        self.device = device
        self.entity_description = desc
        self._attr_translation_key = bsh_key_to_translation_key(self.bsh_key)
        self._attr_unique_id = f"{device.appliance.haId}-{self.bsh_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.appliance.haId)},
            manufacturer=device.appliance.brand,
            model=device.appliance.vib,
            name=device.appliance.name,
        )

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ENTITIES, self._update_callback
            )
        )

    @callback
    def _update_callback(self, ha_id):
        """Update data."""
        if ha_id == self.device.appliance.haId:
            self.async_entity_update()

    @callback
    def async_entity_update(self):
        """Update the entity."""
        _LOGGER.debug("Entity update triggered on %s", self)
        self.async_schedule_update_ha_state(True)

    @property
    def bsh_key(self):
        """Return the BSH key."""
        return self.entity_description.key

    @property
    def status(self) -> dict[str, Any]:
        """Return the status dict of the given BSH key."""
        return self.device.appliance.status.get(self.bsh_key, {})


class HomeConnectInteractiveEntity(HomeConnectEntity):
    """Generic Home Connect entity that can be controlled."""

    async def async_set_value_to_appliance(
        self, value: Any, other_setting: str | None = None
    ) -> bool:
        """Set the native value of the entity."""
        _LOGGER.debug(
            "Tried to set value %s to %s for %s",
            value,
            other_setting if other_setting else self.bsh_key,
            self.entity_id,
        )
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                other_setting if other_setting else self.bsh_key,
                value,
            )
        except HomeConnectError as err:
            _LOGGER.error(
                "Error setting value %s to %s for %s: %s",
                value,
                other_setting if other_setting else self.bsh_key,
                self.entity_id,
                err,
            )
            return False
        return True
