"""Support for Netatmo/Bubendorff button."""

from __future__ import annotations

import logging

from pyatmo import modules as NaModules

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_URL_CONTROL, NETATMO_CREATE_BUTTON
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo button platform."""

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        entity = NetatmoCoverPreferredPositionButton(netatmo_device)
        _LOGGER.debug("Adding button %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BUTTON, _create_entity)
    )


class NetatmoCoverPreferredPositionButton(NetatmoModuleEntity, ButtonEntity):
    """Representation of a Netatmo cover preferred position button device."""

    _attr_configuration_url = CONF_URL_CONTROL
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "preferred_position"
    device: NaModules.Shutter

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize the Netatmo device."""
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
            f"{self.device.entity_id}-{self.device_type}-preferred_position"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        # No state to update for button

    async def async_press(self) -> None:
        """Handle button press to move the cover to a preferred position."""
        _LOGGER.debug("Moving %s to a preferred position", self.device.entity_id)
        await self.device.async_move_to_preferred_position()
