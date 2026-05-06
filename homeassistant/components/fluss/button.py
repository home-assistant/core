"""Support for Fluss Devices."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussApiClientError, FlussConfigEntry
from .entity import FlussEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss buttons for devices without a position sensor."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_buttons() -> None:
        new_entities: list[FlussButton] = []
        for device_id, device in coordinator.data.items():
            if device_id in known or device.has_position_sensor:
                continue
            known.add(device_id)
            new_entities.append(FlussButton(coordinator, device))
        if new_entities:
            async_add_entities(new_entities)

    _add_buttons()
    entry.async_on_unload(coordinator.async_add_listener(_add_buttons))


class FlussButton(FlussEntity, ButtonEntity):
    """Representation of a Fluss button device."""

    _attr_name = None

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.api.async_trigger_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(f"Failed to trigger device: {err}") from err
