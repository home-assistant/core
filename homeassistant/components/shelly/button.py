"""Button for Shelly."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Final, Generic, TypeVar

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import LOGGER, SHELLY_GAS_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .utils import get_device_entry_gen

_ShellyCoordinatorT = TypeVar(
    "_ShellyCoordinatorT", bound=ShellyBlockCoordinator | ShellyRpcCoordinator
)


@dataclass(frozen=True)
class ShellyButtonDescriptionMixin(Generic[_ShellyCoordinatorT]):
    """Mixin to describe a Button entity."""

    press_action: Callable[[_ShellyCoordinatorT], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class ShellyButtonDescription(
    ButtonEntityDescription, ShellyButtonDescriptionMixin[_ShellyCoordinatorT]
):
    """Class to describe a Button entity."""

    supported: Callable[[_ShellyCoordinatorT], bool] = lambda _: True


BUTTONS: Final[list[ShellyButtonDescription[Any]]] = [
    ShellyButtonDescription[ShellyBlockCoordinator | ShellyRpcCoordinator](
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_reboot(),
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="self_test",
        name="Self test",
        icon="mdi:progress-wrench",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda coordinator: coordinator.device.trigger_shelly_gas_self_test(),
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="mute",
        name="Mute",
        icon="mdi:volume-mute",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_shelly_gas_mute(),
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription[ShellyBlockCoordinator](
        key="unmute",
        name="Unmute",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_shelly_gas_unmute(),
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
]


@callback
def async_migrate_unique_ids(
    coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
    entity_entry: er.RegistryEntry,
) -> dict[str, Any] | None:
    """Migrate button unique IDs."""
    if not entity_entry.entity_id.startswith("button"):
        return None

    device_name = slugify(coordinator.device.name)

    for key in ("reboot", "self_test", "mute", "unmute"):
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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    entry_data = get_entry_data(hass)[config_entry.entry_id]
    coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator | None
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        coordinator = entry_data.rpc
    else:
        coordinator = entry_data.block

    if TYPE_CHECKING:
        assert coordinator is not None

    await er.async_migrate_entries(
        hass, config_entry.entry_id, partial(async_migrate_unique_ids, coordinator)
    )

    async_add_entities(
        ShellyButton(coordinator, button)
        for button in BUTTONS
        if button.supported(coordinator)
    )


class ShellyButton(
    CoordinatorEntity[ShellyRpcCoordinator | ShellyBlockCoordinator], ButtonEntity
):
    """Defines a Shelly base button."""

    entity_description: ShellyButtonDescription[
        ShellyRpcCoordinator | ShellyBlockCoordinator
    ]

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
        description: ShellyButtonDescription[
            ShellyRpcCoordinator | ShellyBlockCoordinator
        ],
    ) -> None:
        """Initialize Shelly button."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_name = f"{coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        await self.entity_description.press_action(self.coordinator)
