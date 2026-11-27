"""Support for Vallox ventilation unit switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from vallox_websocket_api import MetricData, Vallox

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
    @override
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self._async_set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        """Update the current value."""
        await self.entity_description.set_fn(self.coordinator.client, on)
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True, kw_only=True)
class ValloxSwitchEntityDescription(SwitchEntityDescription):
    """Describes Vallox switch entity."""

    is_on_fn: Callable[[MetricData], bool | None]
    set_fn: Callable[[Vallox, bool], Awaitable[None]]


SWITCH_ENTITIES: tuple[ValloxSwitchEntityDescription, ...] = (
    ValloxSwitchEntityDescription(
        key="bypass_locked",
        translation_key="bypass_locked",
        is_on_fn=lambda data: data.is_bypass_locked,
        set_fn=lambda client, on: client.set_bypass_locked(on),
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
