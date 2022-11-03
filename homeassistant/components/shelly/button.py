"""Button for Shelly."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import SHELLY_GAS_MODELS
from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .utils import get_block_device_name, get_device_entry_gen, get_rpc_device_name


@dataclass
class ShellyButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable


@dataclass
class ShellyButtonDescription(ButtonEntityDescription, ShellyButtonDescriptionMixin):
    """Class to describe a Button entity."""

    supported: Callable = lambda _: True


BUTTONS: Final = [
    ShellyButtonDescription(
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_reboot(),
    ),
    ShellyButtonDescription(
        key="self_test",
        name="Self Test",
        icon="mdi:progress-wrench",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda coordinator: coordinator.device.trigger_shelly_gas_self_test(),
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription(
        key="mute",
        name="Mute",
        icon="mdi:volume-mute",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.device.trigger_shelly_gas_mute(),
        supported=lambda coordinator: coordinator.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription(
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
        entities = []

        for button in BUTTONS:
            if not button.supported(coordinator):
                continue
            entities.append(ShellyButton(coordinator, button))

        async_add_entities(entities)


class ShellyButton(CoordinatorEntity, ButtonEntity):
    """Defines a Shelly base button."""

    entity_description: ShellyButtonDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator | ShellyBlockCoordinator,
        description: ShellyButtonDescription,
    ) -> None:
        """Initialize Shelly button."""
        super().__init__(coordinator)
        self.entity_description = description

        if isinstance(coordinator, ShellyRpcCoordinator):
            device_name = get_rpc_device_name(coordinator.device)
        else:
            device_name = get_block_device_name(coordinator.device)

        self._attr_name = f"{device_name} {description.name}"
        self._attr_unique_id = slugify(self._attr_name)
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, coordinator.mac)}
        )

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        await self.entity_description.press_action(self.coordinator)
