"""Support for Fluss Devices."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussApiClientError, FlussConfigEntry
from .entity import FlussEntity, has_open_close_sensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fluss Devices, filtering out any invalid payloads."""
    coordinator = entry.runtime_data

    async_add_entities(
        FlussButton(coordinator, device)
        for device in coordinator.data.values()
        if not has_open_close_sensor(device)
    )


class FlussButton(FlussEntity, ButtonEntity):
    """Representation of a Fluss button device."""

    _attr_name = None

    @property
    def available(self) -> bool:
        """Return True only when the device is online."""
        return super().available and self.device.internet_connected

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.api.async_trigger_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(f"Failed to trigger device: {err}") from err
