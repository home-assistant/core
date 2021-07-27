"""Support for TPLink HS100/HS110/HS200 smart switch."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyHS100 import SmartPlug

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.tplink import SmartPlugDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ALIAS, CONF_DEVICE_ID, CONF_MAC, CONF_STATE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_EMETER_PARAMS,
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_SWITCH,
    COORDINATORS,
    DOMAIN as TPLINK_DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entities: list[SmartPlugSwitch] = []
    coordinators: list[SmartPlugDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    switches: list[SmartPlug] = hass.data[TPLINK_DOMAIN][CONF_SWITCH]
    for switch in switches:
        coordinator = coordinators[switch.mac]
        entities.append(SmartPlugSwitch(switch, coordinator))

    async_add_entities(entities)


class SmartPlugSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(
        self, smartplug: SmartPlug, coordinator: DataUpdateCoordinator
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
        return self.data[CONF_DEVICE_ID]

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug."""
        return self.data[CONF_ALIAS]

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.data[CONF_ALIAS],
            "model": self.data[CONF_MODEL],
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.data[CONF_MAC])},
            "sw_version": self.data[CONF_SW_VERSION],
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.data[CONF_STATE]

    def _do_update(self, update_data: dict) -> None:
        """Manually update data."""
        self.coordinator.async_set_updated_data(data={**self.data}.update(update_data))

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.smartplug.turn_on()
        # self._do_update({CONF_STATE: True})
        self.hass.async_add_job(self.coordinator.async_refresh)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.smartplug.turn_off()
        # self._do_update({CONF_STATE: False})
        self.hass.async_add_job(self.coordinator.async_refresh)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the device."""
        return self.data[CONF_EMETER_PARAMS]
