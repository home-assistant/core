"""Assist satellite entity for VoIP integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.assist_satellite import (
    AssistSatelliteEntity,
    AssistSatelliteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import VoIPDevice
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP Assist satellite entity."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoipAssistSatellite(hass, device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    entities: list[VoIPEntity] = [
        VoipAssistSatellite(hass, device) for device in domain_data.devices
    ]

    async_add_entities(entities)


class VoipAssistSatellite(VoIPEntity, AssistSatelliteEntity):
    """Assist satellite for VoIP devices."""

    def __init__(self, hass: HomeAssistant, voip_device: VoIPDevice) -> None:
        """Initialize an Assist satellite."""
        VoIPEntity.__init__(self, voip_device)
        AssistSatelliteEntity.__init__(self)

    @property
    def supported_features(self) -> AssistSatelliteEntityFeature:
        """Return supported features of the satellite."""
        return (
            AssistSatelliteEntityFeature.AUDIO_INPUT
            | AssistSatelliteEntityFeature.AUDIO_OUTPUT
        )

    async def _async_config_updated(self) -> None:
        """Inform when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """
