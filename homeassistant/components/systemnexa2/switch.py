"""Switch entity for the SystemNexa2 integration."""

import logging
from typing import Any

from sn2.device import Device, OnOffSetting

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SystemNexa2Entity
from .helpers import SystemNexa2ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SystemNexa2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights based on a config entry."""
    device = entry.runtime_data.device
    entities: list[SystemNexa2Entity] = [
        ConfigurationSwitch(
            device=entry.runtime_data.device,
            device_info=entry.runtime_data.device_info,
            unique_id=f"setting-{setting.name}",
            name=setting.name,
            entry_id=entry.entry_id,
            setting=setting,
        )
        for setting in device.settings
        if isinstance(setting, OnOffSetting)
    ]

    entry.runtime_data.config_entries.extend(entities)
    if device.info_data and device.info_data.dimmable is False:
        entry.runtime_data.main_entry = SN2SwitchPlug(
            device=device,
            device_info=entry.runtime_data.device_info,
            entry_id=entry.entry_id,
        )
        entities.append(entry.runtime_data.main_entry)
    async_add_entities(entities)


class ConfigurationSwitch(SystemNexa2Entity, SwitchEntity):
    """Configuration switch entity for SystemNexa2 devices."""

    def __init__(
        self,
        device: Device,
        device_info: DeviceInfo,
        name: str,
        entry_id: str,
        unique_id: str,
        setting: OnOffSetting,
    ) -> None:
        """Initialize the configuration switch."""
        super().__init__(
            device,
            entry_id=entry_id,
            unique_entity_id=unique_id,
            device_info=device_info,
            name=name,
        )
        self.entity_description = SwitchEntityDescription(key=unique_id)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_translation_key = name
        self._setting = setting

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        await self._setting.enable(self._device)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        await self._setting.disable(self._device)

    @callback
    def handle_state_update(self, is_on: bool) -> None:
        """Handle state update from the device.

        Updates the entity's native value and writes the new state to Home Assistant
        if the value has changed.

        Args:
            value: The new state value received from the device.
        """
        self._attr_is_on = is_on
        self.async_write_ha_state()


class SN2SwitchPlug(SystemNexa2Entity, SwitchEntity):
    """Representation of a Light."""

    def __init__(self, device: Device, device_info: DeviceInfo, entry_id: str) -> None:
        """Initialize the light."""
        super().__init__(
            device,
            entry_id=entry_id,
            unique_entity_id="switch1",
            name="Switch",
            device_info=device_info,
        )

        self._attr_available = True

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the light."""
        await self._device.turn_on()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the light."""
        await self._device.turn_off()

    async def async_toggle(self, **_kwargs: Any) -> None:
        """Toggle the light."""
        await self._device.toggle()

    @callback
    def handle_state_update(self, *, state: bool) -> None:
        """Handle state updates from the device."""
        if self._attr_is_on != state:
            self._attr_is_on = state
            self.async_write_ha_state()
