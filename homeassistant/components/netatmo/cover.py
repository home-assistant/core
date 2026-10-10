"""Support for Netatmo/Bubendorff covers."""

import logging
from typing import Any, override

from pyatmo import modules as NaModules

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_URL_CONTROL, NETATMO_CREATE_COVER
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
    """Set up the Netatmo cover platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoCover(netatmo_device)
        _LOGGER.debug("Adding cover %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_COVER, _create_entity)
    )


class NetatmoCover(NetatmoReachabilityEntity, CoverEntity):
    """Representation of a Netatmo cover device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_configuration_url = CONF_URL_CONTROL
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None
    device: NaModules.Shutter

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize the Netatmo device."""
        super().__init__(netatmo_device)

        self._attr_is_closed = self.device.current_position == 0

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

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.device.async_close()
        self._attr_is_closed = True
        self.async_write_ha_state()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.device.async_open()
        self._attr_is_closed = False
        self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.device.async_stop()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover shutter to a specific position."""
        await self.device.async_set_target_position(kwargs[ATTR_POSITION])

    @callback
    @override
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if self.device.reachable is not False:
            self._attr_is_closed = self.device.current_position == 0
            self._attr_current_cover_position = self.device.current_position
        self.async_write_ha_state()
