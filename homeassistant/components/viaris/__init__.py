"""Viaris integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the VIARIS integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.info("Unload entry OK")
    else:
        _LOGGER.info("Unload entry not OK")
    return unload_ok


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""

    # Make sure MQTT is available and the entry is loaded

    if not hass.config_entries.async_entries(
        mqtt.DOMAIN
    ) or not await hass.config_entries.async_wait_component(
        hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    ):
        _LOGGER.error("MQTT integration is not available")
        return False

    _LOGGER.info("MQTT integration available")
    return True


@dataclass
class ViarisEntityDescription(EntityDescription):
    """Generic entity description for Viaris."""

    state: Callable | None = None
    attribute: str = "0"
    domain: str = "generic"
    disabled: bool | None = None
    disabled_reason: str | None = None
