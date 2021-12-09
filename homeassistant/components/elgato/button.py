"""Support for Elgato button."""
from __future__ import annotations

import logging

from elgato import Elgato, ElgatoError, Info

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elgato button based on a config entry."""
    elgato: Elgato = hass.data[DOMAIN][entry.entry_id]
    info = await elgato.info()
    async_add_entities([ElgatoIdentifyButton(elgato, info)])


class ElgatoIdentifyButton(ButtonEntity):
    """Defines an Elgato identify button."""

    def __init__(self, elgato: Elgato, info: Info) -> None:
        """Initialize the button entity."""
        self.elgato = elgato
        self._info = info
        self.entity_description = ButtonEntityDescription(
            key="identify",
            name="Identify",
            icon="mdi:help",
            entity_category=ENTITY_CATEGORY_CONFIG,
        )
        self._attr_unique_id = f"{info.serial_number}_{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Elgato Light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._info.serial_number)},
            manufacturer="Elgato",
            model=self._info.product_name,
            name=self._info.product_name,
            sw_version=f"{self._info.firmware_version} ({self._info.firmware_build_number})",
        )

    async def async_press(self) -> None:
        """Identify the light, will make it blink."""
        try:
            await self.elgato.identify()
        except ElgatoError:
            _LOGGER.exception("An error occurred while identifying the Elgato Light")
