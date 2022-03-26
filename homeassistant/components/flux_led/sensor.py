"""Support for Magic Home sensors."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FluxLedUpdateCoordinator
from .entity import FluxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Magic Home sensors."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.device.paired_remotes is not None:
        async_add_entities(
            [
                FluxPairedRemotes(
                    coordinator,
                    entry.unique_id or entry.entry_id,
                    f"{entry.data.get(CONF_NAME, entry.title)} Paired Remotes",
                    "paired_remotes",
                )
            ]
        )


class FluxPairedRemotes(FluxEntity, SensorEntity):
    """Representation of a Magic Home paired remotes sensor."""

    _attr_icon = "mdi:remote"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> int:
        """Return the number of paired remotes."""
        assert self._device.paired_remotes is not None
        return self._device.paired_remotes
