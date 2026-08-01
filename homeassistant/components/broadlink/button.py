"""Button platform for Broadlink remotes."""

from typing import TYPE_CHECKING, override

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SIGNAL_CAPTURE_IR
from .entity import BroadlinkEntity

if TYPE_CHECKING:
    from .device import BroadlinkDevice

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink buttons."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkCaptureInfraredButton(device)])


class BroadlinkCaptureInfraredButton(BroadlinkEntity, ButtonEntity):
    """Button that opens a capture window on the infrared receiver."""

    _attr_has_entity_name = True
    _attr_translation_key = "capture_ir_code"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-capture-ir-code"

    @override
    async def async_press(self) -> None:
        """Ask the infrared receiver to start listening."""
        async_dispatcher_send(
            self.hass, SIGNAL_CAPTURE_IR.format(self._device.unique_id)
        )
