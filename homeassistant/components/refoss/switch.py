"""Switch for Refoss."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from refoss_ha.const import DOMAIN, DEVICE_LIST_COORDINATOR, HA_SWITCH, LOGGER
from refoss_ha.controller.toggle import ToggleXMix
from refoss_ha.controller.device import BaseDevice
from .device import RefossDevice
from . import RefossCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    def entity_adder_callback():
        coordinator: RefossCoordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]

        devicelist = coordinator.find_devices()

        new_entities = []
        try:
            for device in devicelist:
                if not isinstance(device, ToggleXMix):
                    continue

                if len(device.channels) == 0:
                    continue

                for channel in device.channels:
                    w = SwitchEntityWrapper(
                        device=device, channel=channel, coordinator=coordinator
                    )
                    if w.unique_id not in hass.data[DOMAIN]["ADDED_ENTITIES_IDS"]:
                        new_entities.append(w)
        except Exception as e:
            LOGGER.warning(f"setup switch fail,err:{e}")
            raise e

        async_add_entities(new_entities, True)

    coordinator = hass.data[DOMAIN][DEVICE_LIST_COORDINATOR]
    coordinator.async_add_listener(entity_adder_callback)
    entity_adder_callback()


class SwitchDevice(ToggleXMix, BaseDevice):
    pass


class SwitchEntityWrapper(RefossDevice, SwitchEntity):
    device: SwitchDevice

    def __init__(
        self, device: SwitchDevice, channel, coordinator: RefossCoordinator
    ) -> None:
        super().__init__(
            device=device, channel=channel, coordinator=coordinator, platform=HA_SWITCH
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.device.is_on(channel=self._channel_id)

    async def async_update(self):
        await super().async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        LOGGER.info(
            f"Turning on,device_type: {self.device.device_type}, channel: {self._channel_id}"
        )
        await self.device.async_turn_on(self._channel_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        LOGGER.info(
            f"Turning off,device_type: {self.device.device_type}, channel: {self._channel_id}"
        )

        await self.device.async_turn_off(self._channel_id)

    async def async_toggle(self, **kwargs: Any) -> None:
        await self.device.async_toggle(channel=self._channel_id)
