"""Support for Goal Zero Yeti Switches."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GoalZeroEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="v12PortStatus",
        name="12V port status",
    ),
    SwitchEntityDescription(
        key="usbPortStatus",
        name="USB port status",
    ),
    SwitchEntityDescription(
        key="acPortStatus",
        name="AC port status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti switch."""
    async_add_entities(
        GoalZeroSwitch(
            hass.data[DOMAIN][entry.entry_id],
            description,
        )
        for description in SWITCH_TYPES
    )


class GoalZeroSwitch(GoalZeroEntity, SwitchEntity):
    """Representation of a Goal Zero Yeti switch."""

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        return cast(bool, self._api.data[self.entity_description.key] == 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        payload = {self.entity_description.key: 0}
        await self._api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(None)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        payload = {self.entity_description.key: 1}
        await self._api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(None)
