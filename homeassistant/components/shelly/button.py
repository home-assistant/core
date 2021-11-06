"""Button for Shelly."""
from __future__ import annotations

from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import (
    ATTR_BETA,
    BLOCK,
    CONF_OTA_BETA_CHANNEL,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    RPC,
    SERVICE_OTA_UPDATE,
)
from .utils import get_block_device_name, get_device_entry_gen, get_rpc_device_name


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
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
        async_add_entities([ShellyOtaUpdateButton(wrapper, config_entry)])


class ShellyOtaUpdateButton(ButtonEntity):
    """Defines a Shelly OTA update button."""

    _attr_icon = "mdi:sync"
    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(
        self, wrapper: RpcDeviceWrapper | BlockDeviceWrapper, entry: ConfigEntry
    ) -> None:
        """Initialize Shelly OTA update button."""
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, wrapper.mac)}
        )

        if isinstance(wrapper, RpcDeviceWrapper):
            device_name = get_rpc_device_name(wrapper.device)
        else:
            device_name = get_block_device_name(wrapper.device)

        self._attr_name = f"{device_name} OTA Update"
        self._attr_unique_id = slugify(self._attr_name)

        self.entry = entry
        self.wrapper = wrapper

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_OTA_UPDATE,
            {
                ATTR_DEVICE_ID: self.wrapper.device_id,
                ATTR_BETA: self.entry.options.get(CONF_OTA_BETA_CHANNEL),
            },
        )
