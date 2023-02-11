"""Button for Shelly."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Final, Generic, TypeVar

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import SHELLY_GAS_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .utils import get_device_entry_gen

_ShellyCoordinatorT = TypeVar(
    "_ShellyCoordinatorT", bound=ShellyBlockCoordinator | ShellyRpcCoordinator
)


@dataclass
class ShellyButtonDescriptionMixin(Generic[_ShellyCoordinatorT]):
    """Mixin to describe a Button entity."""

    press_action: Callable[[_ShellyCoordinatorT], Coroutine[Any, Any, None]]


@dataclass
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator | None = None
    if get_device_entry_gen(config_entry) == 2:
        coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
    else:
        coordinator = get_entry_data(hass)[config_entry.entry_id].block

    if coordinator is not None:
        entities: list[ShellyButton] = []

        for button in BUTTONS:
            if not button.supported(coordinator):
                continue
            entities.append(ShellyButton(coordinator, button))

        async_add_entities(entities)


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
        self._attr_unique_id = slugify(self._attr_name)
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        await self.entity_description.press_action(self.coordinator)
