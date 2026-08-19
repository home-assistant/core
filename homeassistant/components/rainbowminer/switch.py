"""Switch platform for the RainbowMiner integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RainbowMinerConfigEntry
from .entity import RainbowMinerEntity

PARALLEL_UPDATES = 1

MINING_SWITCH = SwitchEntityDescription(
    key="mining",
    translation_key="mining",
    icon="mdi:pickaxe",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainbowMinerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the RainbowMiner mining switch."""
    coordinator = entry.runtime_data
    async_add_entities([RainbowMinerMiningSwitch(coordinator, MINING_SWITCH)])


class RainbowMinerMiningSwitch(RainbowMinerEntity, SwitchEntity):
    """Switch to pause and resume RainbowMiner mining."""

    entity_description: SwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return True when mining is running (not paused)."""
        return not self.coordinator.data.status.Pause

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume mining."""
        await self.coordinator.api.pause(action="reset")
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause mining."""
        await self.coordinator.api.pause(action="set")
        await self.coordinator.async_request_refresh()
