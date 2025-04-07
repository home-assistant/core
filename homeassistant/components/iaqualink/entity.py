"""Component to embed Aqualink devices."""

from __future__ import annotations

from iaqualink.device import AqualinkDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class AqualinkEntity(Entity):
    """Abstract class for all Aqualink platforms.

    Entity state is updated via the interval timer within the integration.
    Any entity state change via the iaqualink library triggers an internal
    state refresh which is then propagated to all the entities in the system
    via the refresh_system decorator above to the _update_callback in this
    class.
    """

    _attr_should_poll = False

    def __init__(self, dev: AqualinkDevice) -> None:
        """Initialize the entity."""
        self.dev = dev
        self._attr_unique_id = f"{dev.system.serial}_{dev.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=dev.manufacturer,
            model=dev.model,
            name=dev.label,
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from the device."""
        return self.dev.system.online in [False, None]

    @property
    def available(self) -> bool:
        """Return whether the device is available or not."""
        return self.dev.system.online is True
