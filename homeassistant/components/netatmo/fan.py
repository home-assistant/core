"""Support for Netatmo/Bubendorff fans."""

import logging
from typing import Final, override

from pyatmo import modules as NaModules

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_URL_CONTROL, NETATMO_CREATE_FAN
from .coordinator import HOME, SIGNAL_NAME, NetatmoConfigEntry, NetatmoDevice
from .entity import NetatmoReachabilityEntity
from .helper import device_type_to_str

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_PERCENTAGE: Final = 50

PRESET_MAPPING = {"slow": 1, "fast": 2}
PRESETS = {v: k for k, v in PRESET_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo fan platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoFan(netatmo_device)
        _LOGGER.debug("Adding fan %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_FAN, _create_entity)
    )


class NetatmoFan(NetatmoReachabilityEntity, FanEntity):
    """Representation of a Netatmo fan."""

    _attr_preset_modes = ["slow", "fast"]
    _attr_supported_features = FanEntityFeature.PRESET_MODE
    _attr_configuration_url = CONF_URL_CONTROL
    _attr_name = None
    device: NaModules.Fan

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize of Netatmo fan."""
        super().__init__(netatmo_device)
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: f"{HOME}-{self.home.entity_id}",
                },
            ]
        )

        self._attr_unique_id = (
            f"{self.device.entity_id}-{device_type_to_str(self.device_type)}"
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self.device.async_set_fan_speed(PRESET_MAPPING[preset_mode])

    @callback
    @override
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if self.device.reachable is not False:
            if self.device.fan_speed is None:
                self._attr_preset_mode = None
            else:
                self._attr_preset_mode = PRESETS.get(self.device.fan_speed)
        self.async_write_ha_state()
