"""Button  entities for Refoss."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import LOGGER
from .coordinator import RefossConfigEntry, RefossCoordinator


@dataclass(frozen=True, kw_only=True)
class RefossButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_action: Callable[[RefossCoordinator], Coroutine[Any, Any, None]]


REFOSS_BUTTONS: Final[list] = [
    RefossButtonDescription(
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_reboot(),
    ),
    RefossButtonDescription(
        key="fwcheck",
        name="Check latest firmware",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_check_latest_firmware(),
    ),
]


@callback
def async_migrate_unique_ids(
    coordinator: RefossCoordinator,
    entity_entry: er.RegistryEntry,
) -> dict[str, Any] | None:
    """Migrate button unique IDs."""
    if not entity_entry.entity_id.startswith("button"):
        return None

    device_name = slugify(coordinator.device.name)

    for key in ("reboot", "fwcheck"):
        old_unique_id = f"{device_name}_{key}"
        if entity_entry.unique_id == old_unique_id:
            new_unique_id = f"{coordinator.mac}_{key}"
            LOGGER.debug(
                "Migrating unique_id for %s entity from [%s] to [%s]",
                entity_entry.entity_id,
                old_unique_id,
                new_unique_id,
            )
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set buttons for device."""
    entry_data = config_entry.runtime_data
    coordinator: RefossCoordinator | None
    coordinator = entry_data.coordinator

    if TYPE_CHECKING:
        assert coordinator is not None

    await er.async_migrate_entries(
        hass, config_entry.entry_id, partial(async_migrate_unique_ids, coordinator)
    )

    async_add_entities(RefossButton(coordinator, button) for button in REFOSS_BUTTONS)


class RefossButton(CoordinatorEntity[RefossCoordinator], ButtonEntity):
    """Refoss button entity."""

    entity_description: RefossButtonDescription

    def __init__(
        self,
        coordinator: RefossCoordinator,
        description: RefossButtonDescription,
    ) -> None:
        """Initialize Refoss button."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_name = f"{coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

    async def async_press(self) -> None:
        """Triggers the Refoss button press service."""
        await self.entity_description.press_action(self.coordinator)
