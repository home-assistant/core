"""Button for Shelly."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

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
from homeassistant.util import slugify

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC, SHELLY_GAS_MODELS
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
        press_action=lambda wrapper: wrapper.device.trigger_reboot(),
    ),
    ShellyButtonDescription(
        key="self_test",
        name="Self Test",
        icon="mdi:progress-wrench",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_action=lambda wrapper: wrapper.device.trigger_shelly_gas_self_test(),
        supported=lambda wrapper: wrapper.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription(
        key="mute",
        name="Mute",
        icon="mdi:volume-mute",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda wrapper: wrapper.device.trigger_shelly_gas_mute(),
        supported=lambda wrapper: wrapper.device.model in SHELLY_GAS_MODELS,
    ),
    ShellyButtonDescription(
        key="unmute",
        name="Unmute",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda wrapper: wrapper.device.trigger_shelly_gas_unmute(),
        supported=lambda wrapper: wrapper.device.model in SHELLY_GAS_MODELS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    wrapper: RpcDeviceWrapper | BlockDeviceWrapper | None = None
    if get_device_entry_gen(config_entry) == 2:
        if rpc_wrapper := hass.data[DOMAIN][DATA_CONFIG_ENTRY][
            config_entry.entry_id
        ].get(RPC):
            wrapper = cast(RpcDeviceWrapper, rpc_wrapper)
    else:
        if block_wrapper := hass.data[DOMAIN][DATA_CONFIG_ENTRY][
            config_entry.entry_id
        ].get(BLOCK):
            wrapper = cast(BlockDeviceWrapper, block_wrapper)

    if wrapper is not None:
        entities = []

        for button in BUTTONS:
            if not button.supported(wrapper):
                continue
            entities.append(ShellyButton(wrapper, button))

        async_add_entities(entities)


class ShellyButton(ButtonEntity):
    """Defines a Shelly base button."""

    entity_description: ShellyButtonDescription

    def __init__(
        self,
        wrapper: RpcDeviceWrapper | BlockDeviceWrapper,
        description: ShellyButtonDescription,
    ) -> None:
        """Initialize Shelly button."""
        self.entity_description = description
        self.wrapper = wrapper

        if isinstance(wrapper, RpcDeviceWrapper):
            device_name = get_rpc_device_name(wrapper.device)
        else:
            device_name = get_block_device_name(wrapper.device)

        self._attr_name = f"{device_name} {description.name}"
        self._attr_unique_id = slugify(self._attr_name)
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, wrapper.mac)}
        )

    async def async_press(self) -> None:
        """Triggers the Shelly button press service."""
        await self.entity_description.press_action(self.wrapper)
