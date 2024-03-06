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
        translation_key="v12_port_status",
    ),
    SwitchEntityDescription(
        key="usbPortStatus",
        translation_key="usb_port_status",
    ),
    SwitchEntityDescription(
        key="acPortStatus",
        translation_key="ac_port_status",
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
