"""Switch for Refoss."""

from __future__ import annotations

from typing import Any

from refoss_ha.controller.device import BaseDevice
from refoss_ha.controller.toggle import ToggleXMix

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantRefossData
from .const import DOMAIN, LOGGER, REFOSS_DISCOVERY_NEW
from .device import RefossEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """async_setup_entry."""
    hass_data: HomeAssistantRefossData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def entity_add_callback(device_ids: list[str]) -> None:
        """entity_add_callback."""
        new_entities = []
        try:
            for uuid in device_ids:
                device = hass_data.device_manager.base_device_map[uuid]
                if device is None:
                    continue
                if not isinstance(device, ToggleXMix):
                    continue

                if len(device.channels) == 0:
                    continue

                for channel in device.channels:
                    w = SwitchEntityWrapper(device=device, channel=channel)
                    new_entities.append(w)

        except Exception as e:
            LOGGER.debug("setup switch fail,err: %s", e)
            raise e

        async_add_entities(new_entities, True)

    entity_add_callback([*hass_data.device_manager.base_device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, REFOSS_DISCOVERY_NEW, entity_add_callback)
    )


class SwitchDevice(ToggleXMix, BaseDevice):
    """Switch device."""


class SwitchEntityWrapper(RefossEntity, SwitchEntity):
    """Wrapper around SwitchEntity."""

    device: SwitchDevice

    def __init__(self, device: ToggleXMix, channel: int) -> None:
        """Construct."""
        super().__init__(device=device, channel=channel)
        self._channel_id = channel

    @property
    def is_on(self) -> bool | None:
        """is_on."""
        return self.device.is_on(channel=self._channel_id)

    async def async_update(self):
        """async_update."""
        await super().async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """async_turn_on."""
        LOGGER.info(
            f"Turning on,device_type: {self.device.device_type}, channel: {self._channel_id}"
        )
        await self.device.async_turn_on(self._channel_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """async_turn_off."""
        LOGGER.info(
            f"Turning off,device_type: {self.device.device_type}, channel: {self._channel_id}"
        )

        await self.device.async_turn_off(self._channel_id)

    async def async_toggle(self, **kwargs: Any) -> None:
        """async_toggle."""
        await self.device.async_toggle(channel=self._channel_id)
