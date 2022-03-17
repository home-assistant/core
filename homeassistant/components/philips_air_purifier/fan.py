"""The Purifier Fan Entity allows controlling a Philips Air Purifier's fan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .client import FanSpeed, Mode, ReliableClient, Status
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a configured Air Purifier by creating the Fan entity."""
    client = hass.data[DOMAIN][config_entry.entry_id]

    initial_data = {
        "unique_id": config_entry.unique_id,
        "name": config_entry.title,
        "model": config_entry.data["model"],
    }

    entity = PurifierEntity(client, initial_data)
    async_add_entities([entity])


class PurifierEntity(FanEntity):
    """Representation of a Philips air purifier."""

    should_poll: bool = False

    supported_features: int = SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED
    preset_modes: list[str] = [m.name for m in list(Mode) if m != Mode.Manual]
    speeds = [FanSpeed.Speed1, FanSpeed.Speed2, FanSpeed.Speed3, FanSpeed.Turbo]
    speed_count: int = len(speeds)

    def __init__(self, client: ReliableClient, initial_data: dict[str, Any]) -> None:
        """Initialize a PurifierEntity."""
        self._client = client
        self._status: Status | None = None
        # If the device is turned off or not reachable for other reasons, we want the
        # integration to be able to start up anyway and just be unavailable.
        self._initial_data = initial_data

    async def async_added_to_hass(self) -> None:
        """Subscribe to device status updates."""
        self._client.observe_unavailable(id(self), self._set_unavailable)
        self._client.observe_status(id(self), self._set_status)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device status updates."""
        self._client.stop_observing_unavailable(id(self))
        self._client.stop_observing_status(id(self))

    def _set_unavailable(self):
        self._status = None

    def _set_status(self, status: Status) -> None:
        self._status = status
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the unique ID for this purifier."""
        if self._status is None:
            return self._initial_data["unique_id"]
        return self._status.device_id

    @property
    def name(self):
        """Return the purifier's name."""
        if self._status is None:
            return self._initial_data["name"]
        return self._status.name

    @property
    def available(self):
        """Return whether the purifier is available."""
        return self._status is not None

    @property
    def icon(self) -> str | None:
        """Use an air purifier icon instead of the default fan."""
        return "mdi:air-purifier"

    @property
    def device_info(self):
        """
        Return device information for the purifier.

        Given that the purifier is sometimes not responsive for 30 seconds ore more,
        we can't query it during startup and can only use data from the config entry.
        """
        info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Philips",
            "model": self._initial_data["model"],
        }
        _LOGGER.debug("Device info: %s", str(info))
        return info

    @property
    def is_on(self):
        """Return whether the purifier is turned on, i.e. the fan is turning."""
        return self._status.is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the purifier on with a given percentage or preset mode."""
        await self._client.turn_on()

    async def async_turn_off(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn the purifier off."""
        await self._client.turn_off()

    @property
    def preset_mode(self) -> str | None:
        """Return the purifier's preset mode."""
        if self._status is None:
            return None
        if self._status.mode == Mode.Manual:
            return None
        return self._status.mode.name

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate a preset mode on the purifier."""
        mode = Mode[preset_mode]
        await self._client.set_preset_mode(mode)

    device_to_speed_percentage_map = {
        FanSpeed.Off: 0,
        FanSpeed.Silent: 10,
        FanSpeed.Speed1: 25,
        FanSpeed.Speed2: 50,
        FanSpeed.Speed3: 75,
        FanSpeed.Turbo: 100,
    }

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed converted to a percentage."""
        if self._status is None:
            return None
        return self.device_to_speed_percentage_map[self._status.fan_speed]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan to a constant speed."""
        speed = percentage_to_ordered_list_item(self.speeds, percentage)
        await self._client.set_manual_speed(speed)
