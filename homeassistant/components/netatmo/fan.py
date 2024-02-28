"""Support for Netatmo/Bubendorff fans."""
from __future__ import annotations

import logging
from typing import Final, cast

from pyatmo import modules as NaModules

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_URL_CONTROL, NETATMO_CREATE_FAN
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_PERCENTAGE: Final = 50

PRESET_MAPPING = {"slow": 1, "fast": 2}
PRESETS = {v: k for k, v in PRESET_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Netatmo fan platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoFan(netatmo_device)
        _LOGGER.debug("Adding cover %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_FAN, _create_entity)
    )


class NetatmoFan(NetatmoBaseEntity, FanEntity):
    """Representation of a Netatmo fan."""

    _attr_preset_modes = ["slow", "fast"]
    _attr_supported_features = FanEntityFeature.PRESET_MODE

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize of Netatmo fan."""
        super().__init__(netatmo_device.data_handler)

        self._fan = cast(NaModules.Fan, netatmo_device.device)

        self._id = self._fan.entity_id
        self._attr_name = self._device_name = self._fan.name
        self._model = self._fan.device_type
        self._config_url = CONF_URL_CONTROL

        self._home_id = self._fan.home.entity_id

        self._signal_name = f"{HOME}-{self._home_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self._home_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_unique_id = f"{self._id}-{self._model}"

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._fan.async_set_fan_speed(PRESET_MAPPING[preset_mode])

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if self._fan.fan_speed is None:
            self._attr_preset_mode = None
            return
        self._attr_preset_mode = PRESETS.get(self._fan.fan_speed)
