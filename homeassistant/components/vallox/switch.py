"""Support for Vallox ventilation unit switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
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
    ) -> None:
        """Initialize the Vallox switch."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"

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
        await self.coordinator.client.set_values({metric_key: 1 if value else 0})
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
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator = entry.runtime_data

    async_add_entities(
        ValloxSwitchEntity(entry.data[CONF_NAME], coordinator, description)
        for description in SWITCH_ENTITIES
    )
