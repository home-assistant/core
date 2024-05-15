"""Luba lawn mowers."""
from __future__ import annotations

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
    """Set up luba lawn mower."""
    async_add_entities(
        [
            LubaLawnMower(
                "uuid of Luba",
                "Luba (serial number or name)",
                LawnMowerActivity.PAUSED, # find out what state Luba is in
                LawnMowerEntityFeature.DOCK
                | LawnMowerEntityFeature.PAUSE
                | LawnMowerEntityFeature.START_MOWING,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Luba config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class LubaLawnMower(LawnMowerEntity):
    """Representation of a Luba lawn mower."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        activity: LawnMowerActivity,
        features: LawnMowerEntityFeature = LawnMowerEntityFeature(0),
    ) -> None:
        """Initialize the lawn mower."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features
        self._attr_activity = activity

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        self._attr_activity = LawnMowerActivity.MOWING
        self.async_write_ha_state()

    async def async_dock(self) -> None:
        """Start docking."""
        self._attr_activity = LawnMowerActivity.DOCKED
        self.async_write_ha_state()

    async def async_pause(self) -> None:
        """Pause mower."""
        self._attr_activity = LawnMowerActivity.PAUSED
        self.async_write_ha_state()
