"""Select entities for VoIP integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.assist_pipeline.select import AssistPipelineSelect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import VoIPDevice
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoipPipelineSelect(hass, device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [VoipPipelineSelect(hass, device) for device in domain_data.devices]
    )


class VoipPipelineSelect(VoIPEntity, AssistPipelineSelect):
    """Pipeline selector for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a pipeline selector."""
        VoIPEntity.__init__(self, device)
        AssistPipelineSelect.__init__(self, hass, device.voip_id)
