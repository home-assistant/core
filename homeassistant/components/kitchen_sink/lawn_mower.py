"""Demo platform that has a couple fake lawn mowers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo lawn mowers."""
    async_add_entities(
        [
            DemoLawnMower(
                "kitchen_sink_mower_001",
                "Mower can mow",
                LawnMowerActivity.DOCKED_SCHEDULE_ENABLED,
                LawnMowerEntityFeature.START_MOWING,
            ),
            DemoLawnMower(
                "kitchen_sink_mower_002",
                "Mower can dock",
                LawnMowerActivity.MOWING,
                LawnMowerEntityFeature.DOCK,
            ),
            DemoLawnMower(
                "kitchen_sink_mower_003",
                "Mower can pause",
                LawnMowerActivity.DOCKING,
                LawnMowerEntityFeature.PAUSE,
            ),
            DemoLawnMower(
                "kitchen_sink_mower_004",
                "Mower can enable schedule",
                LawnMowerActivity.DOCKED_SCHEDULE_DISABLED,
                LawnMowerEntityFeature.ENABLE_SCHEDULE,
            ),
            DemoLawnMower(
                "kitchen_sink_mower_005",
                "Mower can disable schedule",
                LawnMowerActivity.DOCKED_SCHEDULE_ENABLED,
                LawnMowerEntityFeature.DISABLE_SCHEDULE,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoLawnMower(LawnMowerEntity):
    """Representation of a Demo lawn mower."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: LawnMowerActivity,
        features: LawnMowerEntityFeature = LawnMowerEntityFeature(0),
    ) -> None:
        """Initialize the lawn mower."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features
        self._state = state

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        self._state = LawnMowerActivity.MOWING
        self.async_write_ha_state()

    async def async_dock(self) -> None:
        """Start docking."""
        self._state = LawnMowerActivity.DOCKING
        self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause mower."""
        self._state = LawnMowerActivity.PAUSED
        self.async_write_ha_state()

    async def async_enable_schedule(self, **kwargs: Any) -> None:
        """Set docked schedule enabled."""
        self._state = LawnMowerActivity.DOCKED_SCHEDULE_ENABLED
        self.async_write_ha_state()

    async def async_disable_schedule(self) -> None:
        """Set docked schedule disabled."""
        self._state = LawnMowerActivity.DOCKED_SCHEDULE_DISABLED
        self.async_write_ha_state()
