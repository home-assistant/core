"""The Purifier Fan Entity allows controlling a Philips Air Purifier's fan."""
from __future__ import annotations

import logging
from typing import Any, Final

from phipsair.purifier import FanSpeed, Mode, PersistentClient, Status

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .const import CONF_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_TO_SPEED_PERCENTAGE_MAP: Final = {
    FanSpeed.Off: 0,
    FanSpeed.Silent: 10,
    FanSpeed.Speed1: 25,
    FanSpeed.Speed2: 50,
    FanSpeed.Speed3: 75,
    FanSpeed.Turbo: 100,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a configured Air Purifier by creating the Fan entity."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    entity = PurifierEntity(client, config_entry)
    async_add_entities([entity])


class PurifierEntity(FanEntity):
    """Representation of a Philips air purifier."""

    _attr_should_poll: bool = False

    _attr_supported_features: int = SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED
    _attr_preset_modes: list[str] = [m.name for m in list(Mode) if m != Mode.Manual]
    speeds = [FanSpeed.Speed1, FanSpeed.Speed2, FanSpeed.Speed3, FanSpeed.Turbo]
    _attr_speed_count: int = len(speeds)
    _attr_icon = "mdi:air-purifier"

    def __init__(self, client: PersistentClient, config_entry: ConfigEntry) -> None:
        """Initialize a PurifierEntity."""
        self._client = client
        self._status: Status | None = None
        # If the device is turned off or not reachable for other reasons, we want the
        # integration to be able to start up anyway and just be unavailable.
        self._config_entry = config_entry

        # Make type checker happy below - we always set the unique id
        # in config entries.
        assert config_entry.unique_id is not None

        self._attr_unique_id = self._config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.unique_id)},
            name=config_entry.title,
            manufacturer="Philips",
            model=config_entry.data[CONF_MODEL],
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to device status updates."""
        self._client.observe_status(id(self), self._set_status)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device status updates."""
        self._client.stop_observing_status(id(self))

    def _set_status(self, status: Status | None) -> None:
        """_set_status is a callback passed to PersistentClient to receive push updates."""
        self._status = status
        self.schedule_update_ha_state()

    @property
    def name(self):
        """
        Return the purifier's name.

        Return the config entry title as fallback if it's unavailable, otherwise
        return the name received from the device - it might change over time.
        """
        if self._status is None:
            return self._config_entry.title
        return self._status.name

    @property
    def available(self):
        """Return whether the purifier is available."""
        return self._status is not None

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

        # Make type checker happy. Home Assistant doesn't call this method
        # if the device is unavailable.
        assert self._status is not None

        if self._status.mode == Mode.Manual:
            return None
        return self._status.mode.name

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate a preset mode on the purifier."""
        mode = Mode[preset_mode]
        await self._client.set_preset_mode(mode)

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed converted to a percentage."""

        # Make type checker happy. Home Assistant doesn't call this method
        # if the device is unavailable.
        assert self._status is not None

        return DEVICE_TO_SPEED_PERCENTAGE_MAP[self._status.fan_speed]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan to a constant speed."""
        speed = percentage_to_ordered_list_item(self.speeds, percentage)
        await self._client.set_manual_speed(speed)
