"""Support for Motionblinds button entity using their WLAN API."""

from __future__ import annotations

from motionblinds.motion_blinds import LimitStatus, MotionBlind

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY
from .coordinator import DataUpdateCoordinatorMotionBlinds
from .entity import MotionCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Motionblinds."""
    entities: list[ButtonEntity] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        if blind.limit_status in (
            LimitStatus.Limit3Detected.name,
            {
                "T": LimitStatus.Limit3Detected.name,
                "B": LimitStatus.Limit3Detected.name,
            },
        ):
            entities.append(MotionGoFavoriteButton(coordinator, blind))
            entities.append(MotionSetFavoriteButton(coordinator, blind))

    async_add_entities(entities)


class MotionGoFavoriteButton(MotionCoordinatorEntity, ButtonEntity):
    """Button entity to go to the favorite position of a blind."""

    _attr_translation_key = "go_favorite"

    def __init__(
        self, coordinator: DataUpdateCoordinatorMotionBlinds, blind: MotionBlind
    ) -> None:
        """Initialize the Motion Button."""
        super().__init__(coordinator, blind)
        self._attr_unique_id = f"{blind.mac}-go-favorite"

    async def async_press(self) -> None:
        """Execute the button action."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Go_favorite_position)
        await self.async_request_position_till_stop()


class MotionSetFavoriteButton(MotionCoordinatorEntity, ButtonEntity):
    """Button entity to set the favorite position of a blind to the current position."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "set_favorite"

    def __init__(
        self, coordinator: DataUpdateCoordinatorMotionBlinds, blind: MotionBlind
    ) -> None:
        """Initialize the Motion Button."""
        super().__init__(coordinator, blind)
        self._attr_unique_id = f"{blind.mac}-set-favorite"

    async def async_press(self) -> None:
        """Execute the button action."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Set_favorite_position)
