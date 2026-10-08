"""Base entity for TIS Control."""

from typing import Any, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import TISHub


class TISEntity(Entity):
    """One output channel on one TIS module."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: TISHub, spec: dict[str, Any]) -> None:
        """Initialize the entity."""
        self.hub = hub
        self.address: tuple[int, int] = (spec["subnet"], spec["device"])
        self.channel: int = spec["channel"]
        module_id = f"{hub.entry.entry_id}_{self.address[0]}_{self.address[1]}"
        self._attr_unique_id = f"{module_id}_{self.channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, module_id)},
            name=spec["module"],
            manufacturer="TIS Control",
            model=spec["model"],
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the module answered its last read."""
        return self.hub.is_online(self.address)

    @property
    def level(self) -> int | None:
        """Return the channel level, 0-100."""
        return self.hub.channels.get((*self.address, self.channel))

    @override
    async def async_added_to_hass(self) -> None:
        """Follow updates of this entity's module."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hub.subscribe(self.address, self.async_write_ha_state)
        )
