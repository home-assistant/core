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
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC
from .utils import get_block_device_name, get_device_entry_gen, get_rpc_device_name


@dataclass
class ShellyButtonDescriptionMixin:
    """Mixin to describe a Button entity."""

    press_action: Callable


@dataclass
class ShellyButtonDescription(ButtonEntityDescription, ShellyButtonDescriptionMixin):
    """Class to describe a Button entity."""


BUTTONS: Final = [
    ShellyButtonDescription(
        key="ota_update",
        name="OTA Update",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=ENTITY_CATEGORY_CONFIG,
        press_action=lambda wrapper: wrapper.async_trigger_ota_update(),
    ),
    ShellyButtonDescription(
        key="ota_update_beta",
        name="OTA Update Beta",
        device_class=ButtonDeviceClass.UPDATE,
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_CONFIG,
        press_action=lambda wrapper: wrapper.async_trigger_ota_update(beta=True),
    ),
    ShellyButtonDescription(
        key="reboot",
        name="Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=ENTITY_CATEGORY_CONFIG,
        press_action=lambda wrapper: wrapper.device.trigger_reboot(),
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
        async_add_entities([ShellyButton(wrapper, button) for button in BUTTONS])


class ShellyButton(ButtonEntity):
    """Defines a Shelly OTA update base button."""

    entity_description: ShellyButtonDescription

    def __init__(
        self,
        wrapper: RpcDeviceWrapper | BlockDeviceWrapper,
        description: ShellyButtonDescription,
    ) -> None:
        """Initialize Shelly OTA update button."""
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
        """Triggers the OTA update service."""
        await self.entity_description.press_action(self.wrapper)
