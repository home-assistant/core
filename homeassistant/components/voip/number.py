"""Number entities for VoIP integration."""

from homeassistant.components.assist_pipeline import (
    VadSilenceSecondsNumber,
    VadTimeoutSecondsNumber,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VoipConfigEntry
from .devices import VoIPDevice
from .entity import VoIPEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VoipConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP number entities."""
    domain_data = config_entry.runtime_data.domain_data

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities(
            [
                VoipVadSilenceSecondsNumber(hass, device),
                VoipVadTimeoutSecondsNumber(hass, device),
            ]
        )

    domain_data.devices.async_add_new_device_listener(async_add_device)

    entities: list[VoIPEntity] = []
    for device in domain_data.devices:
        entities.append(VoipVadSilenceSecondsNumber(hass, device))
        entities.append(VoipVadTimeoutSecondsNumber(hass, device))

    async_add_entities(entities)


class VoipVadSilenceSecondsNumber(VoIPEntity, VadSilenceSecondsNumber):
    """VAD silence seconds for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a VAD silence seconds number."""
        VoIPEntity.__init__(self, device)
        VadSilenceSecondsNumber.__init__(self, hass, device.voip_id)


class VoipVadTimeoutSecondsNumber(VoIPEntity, VadTimeoutSecondsNumber):
    """VAD timeout seconds for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a VAD timeout seconds number."""
        VoIPEntity.__init__(self, device)
        VadTimeoutSecondsNumber.__init__(self, hass, device.voip_id)
