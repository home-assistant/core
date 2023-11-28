"""Select entities for VoIP integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.assist_pipeline.select import AssistPipelineSelect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WyomingSatelliteEntity
from .satellite.devices import SatelliteDevice

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_device(device: SatelliteDevice) -> None:
        """Add device."""
        async_add_entities([WyomingSatellitePipelineSelect(hass, device)])

    domain_data.satellite_devices.async_add_new_device_listener(async_add_device)

    entities: list[WyomingSatelliteEntity] = []
    for device in domain_data.satellite_devices:
        entities.append(WyomingSatellitePipelineSelect(hass, device))

    async_add_entities(entities)


class WyomingSatellitePipelineSelect(WyomingSatelliteEntity, AssistPipelineSelect):
    """Pipeline selector for Wyoming satellites."""

    def __init__(self, hass: HomeAssistant, device: SatelliteDevice) -> None:
        """Initialize a pipeline selector."""
        self.device = device

        WyomingSatelliteEntity.__init__(self, device)
        AssistPipelineSelect.__init__(self, hass, device.satellite_id)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await super().async_select_option(option)
        self.device.async_pipeline_changed()
