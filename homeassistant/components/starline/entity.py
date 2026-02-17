"""StarLine base entity."""

from __future__ import annotations

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._account.api.available

    def update(self) -> None:
        """Read new state data."""
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(self._account.api.add_update_listener(self.update))
