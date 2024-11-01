"""Support for Vallox ventilation unit switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vallox_websocket_api import Vallox

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ValloxDataUpdateCoordinator
from .entity import ValloxEntity


class ValloxSwitchEntity(ValloxEntity, SwitchEntity):
    """Representation of a Vallox switch."""

    entity_description: ValloxSwitchEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxSwitchEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox switch."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if (
            value := self.coordinator.data.get(self.entity_description.metric_key)
        ) is None:
            return None
        return value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self._set_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        """Update the current value."""
        metric_key = self.entity_description.metric_key
        await self._client.set_values({metric_key: 1 if value else 0})
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True, kw_only=True)
class ValloxSwitchEntityDescription(SwitchEntityDescription):
    """Describes Vallox switch entity."""

    metric_key: str


SWITCH_ENTITIES: tuple[ValloxSwitchEntityDescription, ...] = (
    ValloxSwitchEntityDescription(
        key="bypass_locked",
        translation_key="bypass_locked",
        metric_key="A_CYC_BYPASS_LOCKED",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ValloxSwitchEntity(
            data["name"], data["coordinator"], description, data["client"]
        )
        for description in SWITCH_ENTITIES
    )
