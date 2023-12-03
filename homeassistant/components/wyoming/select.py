"""Select entities for VoIP integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.assist_pipeline.select import AssistPipelineSelect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import SatelliteDevice
from .entity import WyomingSatelliteEntity

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.satellite is not None

    async_add_entities([WyomingSatellitePipelineSelect(hass, item.satellite.device)])


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
        self.device.set_pipeline_name(option)
