"""Support for Imou button controls."""

from __future__ import annotations

import logging

from pyimouapi.exceptions import ImouException

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ImouConfigEntry
from .const import PARAM_RESTART_DEVICE, PARAM_ROTATION_DURATION
from .entity import ImouEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou button entities.

    Args:
        hass: Home Assistant core object
        entry: Configuration entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up button entities")
    imou_entry: ImouConfigEntry = entry
    imou_coordinator = imou_entry.runtime_data
    entities = []
    for device in imou_coordinator.devices:
        for button_type in device.buttons:
            button_entity = ImouButton(
                imou_coordinator,
                entry,
                button_type,
                device,
            )
            entities.append(button_entity)
    if entities:
        async_add_entities(entities)


class ImouButton(ImouEntity, ButtonEntity):
    """Imou button entity."""

    async def async_press(self) -> None:
        """Handle button press.

        Uses the rotation duration from config entry options.
        """
        await self._async_do_press(
            self._config_entry.options.get(PARAM_ROTATION_DURATION, 500)
        )

    @property
    def device_class(self) -> ButtonDeviceClass | None:
        """Return the device class.

        Returns:
            Button device class, or None if not applicable
        """
        if self._entity_type == PARAM_RESTART_DEVICE:
            return ButtonDeviceClass.RESTART
        return None

    async def _async_do_press(self, duration: int) -> None:
        """Execute button press operation.

        Args:
            duration: Duration in milliseconds

        Raises:
            HomeAssistantError: If the operation fails
        """
        try:
            await self._coordinator.device_manager.async_press_button(
                self._device,
                self._entity_type,
                duration,
            )
        except ImouException as e:
            raise HomeAssistantError(e.message) from e
