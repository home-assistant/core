"""StarLine base entity."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.helpers.entity import Entity

from .account import StarlineAccount, StarlineDevice


class StarlineEntity(Entity):
    """StarLine base entity class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, account: StarlineAccount, device: StarlineDevice, key: str
    ) -> None:
        """Initialize StarLine entity."""
        self._account = account
        self._device = device
        self._key = key
        self._attr_unique_id = f"starline-{key}-{device.device_id}"
        self._attr_device_info = account.device_info(device)
        self._unsubscribe_api: Callable | None = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._account.api.available

    def update(self):
        """Read new state data."""
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._unsubscribe_api = self._account.api.add_update_listener(self.update)

    async def async_will_remove_from_hass(self):
        """Call when entity is being removed from Home Assistant."""
        await super().async_will_remove_from_hass()
        if self._unsubscribe_api is not None:
            self._unsubscribe_api()
            self._unsubscribe_api = None
