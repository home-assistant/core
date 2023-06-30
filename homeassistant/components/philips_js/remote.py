"""Remote control support for Apple TV."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LOGGER, PhilipsTVDataUpdateCoordinator
from .const import DOMAIN
from .helpers import async_get_turn_on_trigger


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([PhilipsTVRemote(coordinator)])


class PhilipsTVRemote(CoordinatorEntity[PhilipsTVDataUpdateCoordinator], RemoteEntity):
    """Device that sends commands."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize the Philips TV."""
        super().__init__(coordinator)
        self._tv = coordinator.api
        self._attr_name = "Remote"
        self._attr_unique_id = coordinator.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            },
            manufacturer="Philips",
            model=coordinator.system.get("model"),
            name=coordinator.system["name"],
            sw_version=coordinator.system.get("softwareversion"),
        )
        self._turn_on = PluggableAction(self.async_write_ha_state)

    async def async_added_to_hass(self) -> None:
        """Handle being added to hass."""
        await super().async_added_to_hass()

        if (entry := self.registry_entry) and entry.device_id:
            self.async_on_remove(
                self._turn_on.async_register(
                    self.hass, async_get_turn_on_trigger(entry.device_id)
                )
            )

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return bool(
            self._tv.on and (self._tv.powerstate == "On" or self._tv.powerstate is None)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._tv.on and self._tv.powerstate:
            await self._tv.setPowerState("On")
        else:
            await self._turn_on.async_run(self.hass, self._context)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._tv.on:
            await self._tv.sendKey("Standby")
            self.async_write_ha_state()
        else:
            LOGGER.debug("Tv was already turned off")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to one device."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                LOGGER.debug("Sending command %s", single_command)
                await self._tv.sendKey(single_command)
                await asyncio.sleep(delay)
