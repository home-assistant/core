"""Support for TPLink HS100/HS110/HS200 smart switch."""
from __future__ import annotations

from asyncio import sleep

import logging
from typing import Any

from kasa import SmartDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.tplink import TPLinkDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_SW_VERSION, CONF_SWITCH, COORDINATORS, DOMAIN as TPLINK_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entities: list[SmartPlugSwitch] = []
    coordinators: list[TPLinkDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    switches: list[SmartDevice] = hass.data[TPLINK_DOMAIN][CONF_SWITCH]
    for switch in switches:
        coordinator = coordinators[switch.device_id]
        entities.append(SmartPlugSwitch(switch, coordinator))
        if switch.is_strip:
            _LOGGER.info("initializing strip with %s sockets", len(switch.children))
            for child in switch.children:
                entities.append(SmartPlugSwitch(child, coordinator))

    async_add_entities(entities)


class SmartPlugSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(
        self, smartplug: SmartDevice, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.smartplug = smartplug

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.smartplug.device_id

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug."""
        return self.smartplug.alias

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        data = {
            "name": self.smartplug.alias,
            "model": self.smartplug.model,
            "manufacturer": "TP-Link",
            # Note: mac instead of device_id here to connect subdevices to the main device
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.smartplug.mac)},
            "sw_version": self.data[CONF_SW_VERSION],
        }

        return data

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.smartplug.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.smartplug.turn_on()
        # Workaround for delayed device state update on HS210: #55190
        if "HS210" in self.smartplug.model:
            await sleep(0.5)

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.smartplug.turn_off()
        # Workaround for delayed device state update on HS210: #55190
        if "HS210" in self.smartplug.model:
            await sleep(0.5)

        await self.coordinator.async_refresh()
