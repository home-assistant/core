"""2N Telekomunikace switch platform."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, cast

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Py2NDevice, Py2NDeviceCoordinator, Py2NDeviceEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class Py2NDeviceSwitchRequiredKeysMixin:
    """Class for 2N Telekomunikace entity required keys."""

    switch_id: int


@dataclass
class Py2NDeviceSwitchEntityDescription(
    SwitchEntityDescription, Py2NDeviceSwitchRequiredKeysMixin
):
    """A class that describes switch entities."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator: Py2NDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = []
    for switch in coordinator.device.data.switches:
        description = Py2NDeviceSwitchEntityDescription(
            key=f"switch_{switch.id}",
            name=f"Switch {switch.id}",
            device_class=SwitchDeviceClass.SWITCH,
            switch_id=switch.id,
        )

        switches.append(Py2NDeviceSwitch(coordinator, description, coordinator.device))

    async_add_entities(switches, False)


class Py2NDeviceSwitch(Py2NDeviceEntity, SwitchEntity):
    """Define a 2N Telekomunikace switch."""

    entity_description: Py2NDeviceSwitchEntityDescription
    internal_on: bool | None = None

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: Py2NDeviceSwitchEntityDescription,
        device: Py2NDevice,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description, device)

    @property
    def is_on(self) -> bool:
        """Return current switch state."""
        if self.internal_on:
            return cast(bool, self.internal_on)

        return bool(
            self.coordinator.device.get_switch(self.entity_description.switch_id)
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        await self.set_state(True)
        self.internal_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        await self.set_state(False)
        self.internal_on = False
        self.async_write_ha_state()

    async def set_state(self, state: bool) -> None:
        """Set switch state."""
        _LOGGER.debug("Setting state for entity %s, state: %s", self.name, state)
        await self.safe_request(
            lambda: self.device.set_switch(self.entity_description.switch_id, state)
        )

    @callback
    def _update_callback(self) -> None:
        self.internal_on = None
        super()._update_callback()
