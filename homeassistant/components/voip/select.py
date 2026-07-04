"""Select entities for VoIP integration."""

from homeassistant.components.assist_pipeline import (
    AssistPipelineSelect,
    VadSensitivitySelect,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VoipConfigEntry
from .const import DOMAIN
from .devices import VoIPDevice
from .entity import VoIPEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VoipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    domain_data = config_entry.runtime_data.domain_data

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities(
            [VoipPipelineSelect(hass, device), VoipVadSensitivitySelect(hass, device)]
        )

    domain_data.devices.async_add_new_device_listener(async_add_device)

    entities: list[VoIPEntity] = []
    for device in domain_data.devices:
        entities.append(VoipPipelineSelect(hass, device))
        entities.append(VoipVadSensitivitySelect(hass, device))

    async_add_entities(entities)


class VoipPipelineSelect(VoIPEntity, AssistPipelineSelect):
    """Pipeline selector for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a pipeline selector."""
        VoIPEntity.__init__(self, device)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, device.voip_id)


class VoipVadSensitivitySelect(VoIPEntity, VadSensitivitySelect):
    """VAD sensitivity selector for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a VAD sensitivity selector."""
        VoIPEntity.__init__(self, device)
        VadSensitivitySelect.__init__(self, hass, device.voip_id)
