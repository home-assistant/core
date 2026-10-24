"""Switch platform for Acaia scales."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity

PARALLEL_UPDATES = 0

KEEP_CONNECTED_DESCRIPTION = SwitchEntityDescription(
    key="keep_connected",
    translation_key="keep_connected",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""

    coordinator = entry.runtime_data
    async_add_entities(
        [AcaiaKeepConnectedSwitch(coordinator, KEEP_CONNECTED_DESCRIPTION)]
    )


class AcaiaKeepConnectedSwitch(AcaiaEntity, SwitchEntity):
    """Switch to keep a persistent connection to the scale between brews."""

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the scale is kept connected."""
        return self.coordinator.keep_connected

    @property
    @override
    def available(self) -> bool:
        """This switch controls connectivity itself, so it stays available."""
        return self.coordinator.last_update_success

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Keep the scale connected."""
        await self.coordinator.async_set_keep_connected(True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Allow the scale to disconnect and go to sleep on its own."""
        await self.coordinator.async_set_keep_connected(False)
        self.async_write_ha_state()
