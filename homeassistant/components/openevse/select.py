"""Support for OpenEVSE select entities."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp import OpenEVSE

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import ATTR_CONNECTIONS, ATTR_SERIAL_NUMBER, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator
from .helpers import openevse_exception_handler

PARALLEL_UPDATES = 0

OVERRIDE_STATE_OPTIONS: list[str] = ["auto", "active", "disabled"]


async def _async_set_override_state(charger: OpenEVSE, option: str) -> None:
    """Set the override state on the charger."""
    if option == "auto":
        await charger.clear_override()
    else:
        await charger.set_override(state=option)


@dataclass(frozen=True, kw_only=True)
class OpenEVSESelectDescription(SelectEntityDescription):
    """Describes an OpenEVSE select entity."""

    current_option_fn: Callable[[OpenEVSE], Awaitable[str | None]]
    select_option_fn: Callable[[OpenEVSE, str], Awaitable[Any]]


SELECT_TYPES: tuple[OpenEVSESelectDescription, ...] = (
    OpenEVSESelectDescription(
        key="override_state",
        translation_key="override_state",
        entity_category=EntityCategory.CONFIG,
        options=OVERRIDE_STATE_OPTIONS,
        current_option_fn=lambda ev: ev.get_override_state(),
        select_option_fn=_async_set_override_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE selects based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSESelect(coordinator, description, identifier, entry.unique_id)
        for description in SELECT_TYPES
    )


class OpenEVSESelect(CoordinatorEntity[OpenEVSEDataUpdateCoordinator], SelectEntity):
    """Implementation of an OpenEVSE select entity."""

    _attr_has_entity_name = True
    entity_description: OpenEVSESelectDescription
    _attr_current_option: str | None = None
    _update_task: asyncio.Task[None] | None = None

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSESelectDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._attr_current_option is not None

    async def _async_update_current_option(self) -> None:
        """Update the current option from the charger."""
        with openevse_exception_handler():
            self._attr_current_option = await self.entity_description.current_option_fn(
                self.coordinator.charger
            )

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        await self._async_update_current_option()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        if self._update_task is None or self._update_task.done():
            self._update_task = self.hass.async_create_task(
                self._async_update_and_write_ha_state()
            )

    async def _async_update_and_write_ha_state(self) -> None:
        """Fetch updated option and write HA state."""
        await self._async_update_current_option()
        self.async_write_ha_state()

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        with openevse_exception_handler(option):
            await self.entity_description.select_option_fn(
                self.coordinator.charger, option
            )
        self._attr_current_option = option
        self.async_write_ha_state()
