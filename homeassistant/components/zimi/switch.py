"""Platform for switch integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support.
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Switch platform."""

    debug = config_entry.data.get("debug", False)

    controller: ZimiController = hass.data[CONTROLLER]

    entities = []

    # for key, device in controller.api.devices.items():
    for device in controller.controller.outlets:
        entities.append(ZimiSwitch(device, debug=debug))  # noqa: PERF401

    async_add_entities(entities)


class ZimiSwitch(SwitchEntity):
    """Representation of an Zimi Switch."""

    def __init__(self, switch, debug=False) -> None:
        """Initialize an ZimiSwitch."""

        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        self._attr_unique_id = switch.identifier
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:power-socket-au"
        self._attr_should_poll = False
        self._switch = switch
        self._switch.subscribe(self)
        self._state = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, switch.identifier)},
            name=self._switch.name,
            suggested_area=self._switch.room,
        )
        self.update()
        self.logger.debug("__init__(%s) in %s", self.name, self._switch.room)

    def __del__(self):
        """Cleanup ZimiSwitchwith removal of notification."""
        self._switch.unsubscribe(self)

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._switch.is_connected

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._name.strip()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    def notify(self, _observable):
        """Receive notification from switch device that state has changed."""

        self.logger.debug("notification() for %s received", self.name)
        self.schedule_update_ha_state(force_refresh=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""

        self.logger.debug("turn_on() for %s", self.name)

        await self._switch.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""

        self.logger.debug("turn_off() for %s", self.name)

        await self._switch.turn_off()

    def update(self) -> None:
        """Fetch new state data for this switch."""

        self._name = self._switch.name
        self._state = self._switch.is_on
        self._attr_is_on = self._switch.is_on
