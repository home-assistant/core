"""Demo platform for the lawn mower component."""

from datetime import datetime
from typing import override

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

SUPPORTED_SERVICES = (
    LawnMowerEntityFeature.START_MOWING
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.STOP
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            StateDemoLawnMower("lawn_mower_1", "My Lawn Mower", SUPPORTED_SERVICES),
        ]
    )


class StateDemoLawnMower(LawnMowerEntity):
    """Representation of a demo lawn mower."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "model_s"

    def __init__(
        self, unique_id: str, name: str, supported_features: LawnMowerEntityFeature
    ) -> None:
        """Initialize the lawn mower."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = supported_features
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )
        self._attr_activity = LawnMowerActivity.DOCKED

    @override
    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        self._attr_activity = LawnMowerActivity.MOWING
        self.async_write_ha_state()

    @override
    async def async_dock(self) -> None:
        """Dock the mower."""
        self._attr_activity = LawnMowerActivity.RETURNING
        self.async_write_ha_state()
        self.async_on_remove(
            event.async_call_later(self.hass, 5, self.__set_state_to_dock)
        )

    @override
    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        self._attr_activity = LawnMowerActivity.PAUSED
        self.async_write_ha_state()

    @override
    async def async_stop(self) -> None:
        """Stop the lawn mower."""
        self._attr_activity = LawnMowerActivity.IDLE
        self.async_write_ha_state()

    def __set_state_to_dock(self, _: datetime) -> None:
        """Called later to set the state to docked."""
        self._attr_activity = LawnMowerActivity.DOCKED
        self.schedule_update_ha_state()
