"""Obihai button module."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .connectivity import ObihaiConnection
from .const import OBIHAI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Obihai sensor entries."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    host = entry.data[CONF_HOST]
    requester = ObihaiConnection(host, username, password)

    await hass.async_add_executor_job(requester.update)
    buttons = [ObihaiButton(requester.pyobihai, requester.serial)]
    async_add_entities(buttons, update_before_add=True)


class ObihaiButton(ButtonEntity):
    """Obihai Reboot button."""

    def __init__(self, pyobihai: PyObihai, serial: str) -> None:
        """Initialize monitor sensor."""
        self._pyobihai = pyobihai
        self._attr_unique_id = f"{serial}-reboot"
        self.entity_description = ButtonEntityDescription(
            key="reboot",
            name=f"{OBIHAI} Reboot",
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.CONFIG,
        )

    def press(self) -> None:
        """Press button."""

        try:
            result = self._pyobihai.call_reboot()
            if not result:
                _LOGGER.debug("Button press failed!")
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Button press has returned an exception: %s", ex)
