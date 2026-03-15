"""Support for TRMNL switch entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from trmnl.models import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TRMNLConfigEntry
from .coordinator import TRMNLCoordinator
from .entity import TRMNLEntity, exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TRMNLSwitchEntityDescription(SwitchEntityDescription):
    """Describes a TRMNL switch entity."""

    value_fn: Callable[[Device], bool]
    set_value_fn: Callable[[TRMNLCoordinator, int, bool], Coroutine[Any, Any, None]]


SWITCH_DESCRIPTIONS: tuple[TRMNLSwitchEntityDescription, ...] = (
    TRMNLSwitchEntityDescription(
        key="sleep_mode",
        translation_key="sleep_mode",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.sleep_mode_enabled,
        set_value_fn=lambda coordinator, device_id, value: (
            coordinator.client.update_device(device_id, sleep_mode_enabled=value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TRMNLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TRMNL switch entities based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data) - known_device_ids
        if new_ids:
            async_add_entities(
                TRMNLSwitchEntity(coordinator, device_id, description)
                for device_id in new_ids
                for description in SWITCH_DESCRIPTIONS
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TRMNLSwitchEntity(TRMNLEntity, SwitchEntity):
    """Defines a TRMNL switch entity."""

    entity_description: TRMNLSwitchEntityDescription

    def __init__(
        self,
        coordinator: TRMNLCoordinator,
        device_id: int,
        description: TRMNLSwitchEntityDescription,
    ) -> None:
        """Initialize TRMNL switch entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if sleep mode is enabled."""
        return self.entity_description.value_fn(self._device)

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable sleep mode."""
        await self.entity_description.set_value_fn(
            self.coordinator, self._device_id, True
        )
        await self.coordinator.async_request_refresh()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable sleep mode."""
        await self.entity_description.set_value_fn(
            self.coordinator, self._device_id, False
        )
        await self.coordinator.async_request_refresh()
