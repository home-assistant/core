"""Support for Netatmo/BTicino/Legrande switches."""

import logging
from typing import Any, override

from pyatmo import modules as NaModules

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_URL_CONTROL, NETATMO_CREATE_SWITCH
from .coordinator import HOME, SIGNAL_NAME, NetatmoConfigEntry, NetatmoDevice
from .entity import NetatmoReachabilityEntity
from .helper import device_type_to_str

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetatmoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo switch platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoSwitch(netatmo_device)
        _LOGGER.debug("Adding switch %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SWITCH, _create_entity)
    )


class NetatmoSwitch(NetatmoReachabilityEntity, SwitchEntity):
    """Representation of a Netatmo switch device."""

    _attr_name = None
    _attr_configuration_url = CONF_URL_CONTROL
    device: NaModules.Switch

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
    ) -> None:
        """Initialize the Netatmo device."""
        super().__init__(netatmo_device)
        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )
        self._attr_unique_id = (
            f"{self.device.entity_id}-{device_type_to_str(self.device_type)}"
        )
        self._attr_is_on = self.device.on

    @callback
    @override
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if self.device.reachable is not False:
            self._attr_is_on = self.device.on
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.device.async_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.device.async_off()
        self._attr_is_on = False
        self.async_write_ha_state()
