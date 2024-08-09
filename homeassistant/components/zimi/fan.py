"""Platform for fan integration."""
# mypy: ignore-errors

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support.
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Cover platform."""

    debug = config_entry.data.get("debug", False)

    controller: ZimiController = hass.data[CONTROLLER]

    entities = []

    # for key, device in controller.api.devices.items().:
    for device in controller.controller.fans:
        entities.append(ZimiFan(device, debug=debug))  # noqa: PERF401

    async_add_entities(entities)


class ZimiFan(FanEntity):
    """Representation of a Zimi fan."""

    def __init__(self, fan, debug=False) -> None:
        """Initialize an ZimiFan."""

        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        self._attr_unique_id = fan.identifier
        self._attr_should_poll = False
        self._attr_supported_features = FanEntityFeature.SET_SPEED
        self._fan = fan
        self._fan.subscribe(self)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, fan.identifier)},
            name=self._fan.name,
            suggested_area=self._fan.room,
        )
        self._speed = self._fan.fanspeed
        self.update()
        self.logger.debug("__init__(%s) in %s", self.name, self._fan.room)

    def __del__(self):
        """Cleanup ZimiCover with removal of notification."""
        self._fan.unsubscribe(self)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the desired speed for the fan."""
        self.logger.debug("async_set_percentage() with percentage %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        target_speed = math.ceil(
            percentage_to_ranged_value(self._speed_range, percentage)
        )
        self.logger.debug(
            "async_set_percentage() converted percentage %s to bond speed %s",
            percentage,
            target_speed,
        )

        await self._fan.set_fanspeed(target_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Instruct the fan to turn on."""

        self.logger.debug("turn_on() for %s", self.name)
        await self._fan.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        self.logger.debug("turn_off() for %s", self.name)
        await self._fan.turn_off()

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._fan.is_connected

    @property
    def name(self) -> str:
        """Return the display name of this cover."""
        return self._name.strip()

    def notify(self, _observable):
        """Receive notification from cover device that state has changed."""

        self.logger.debug("notification() for %s received", self.name)
        self.schedule_update_ha_state(force_refresh=True)

    @property
    def percentage(self) -> int:
        """Return the current speed percentage for the fan."""
        if not self._speed:
            return 0
        return ranged_value_to_percentage(self._speed_range, self._speed)

    @property
    def _speed_range(self) -> tuple[int, int]:
        """Return the range of speeds."""
        return (0, 7)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    def update(self) -> None:
        """Fetch new state data for this cover."""

        self._name = self._fan.name
        self._speed = self._fan.fanspeed
