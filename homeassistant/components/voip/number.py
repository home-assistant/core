"""Number entities for VoIP integration."""

from homeassistant.components.assist_pipeline import CommandTimeoutNumber
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
        async_add_entities([VoipCommandTimeoutNumber(hass, device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [VoipCommandTimeoutNumber(hass, device) for device in domain_data.devices]
    )


class VoipCommandTimeoutNumber(VoIPEntity, CommandTimeoutNumber):
    """Command timeout for VoIP devices."""

    def __init__(self, hass: HomeAssistant, device: VoIPDevice) -> None:
        """Initialize a command timeout number."""
        VoIPEntity.__init__(self, device)
        CommandTimeoutNumber.__init__(self, hass, device.voip_id)
