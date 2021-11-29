"""Button for Shelly."""
from __future__ import annotations

from typing import cast

from homeassistant.components.button import ButtonEntity
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
        async_add_entities(
            [
                ShellyOtaUpdateStableButton(wrapper, config_entry),
                ShellyOtaUpdateBetaButton(wrapper, config_entry),
            ]
        )


class ShellyOtaUpdateBaseButton(ButtonEntity):
    """Defines a Shelly OTA update base button."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(
        self,
        wrapper: RpcDeviceWrapper | BlockDeviceWrapper,
        entry: ConfigEntry,
        name: str,
        beta_channel: bool,
        icon: str,
    ) -> None:
        """Initialize Shelly OTA update button."""
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, wrapper.mac)}
        )

        if isinstance(wrapper, RpcDeviceWrapper):
            device_name = get_rpc_device_name(wrapper.device)
        else:
            device_name = get_block_device_name(wrapper.device)

        self._attr_name = f"{device_name} {name}"
        self._attr_unique_id = slugify(self._attr_name)
        self._attr_icon = icon

        self.beta_channel = beta_channel
        self.entry = entry
        self.wrapper = wrapper

    async def async_press(self) -> None:
        """Triggers the OTA update service."""
        await self.wrapper.async_trigger_ota_update(beta=self.beta_channel)


class ShellyOtaUpdateStableButton(ShellyOtaUpdateBaseButton):
    """Defines a Shelly OTA update stable channel button."""

    def __init__(
        self, wrapper: RpcDeviceWrapper | BlockDeviceWrapper, entry: ConfigEntry
    ) -> None:
        """Initialize Shelly OTA update button."""
        super().__init__(wrapper, entry, "OTA Update", False, "mdi:package-up")


class ShellyOtaUpdateBetaButton(ShellyOtaUpdateBaseButton):
    """Defines a Shelly OTA update beta channel button."""

    def __init__(
        self, wrapper: RpcDeviceWrapper | BlockDeviceWrapper, entry: ConfigEntry
    ) -> None:
        """Initialize Shelly OTA update button."""
        super().__init__(wrapper, entry, "OTA Update Beta", True, "mdi:flask-outline")
        self._attr_entity_registry_enabled_default = False
