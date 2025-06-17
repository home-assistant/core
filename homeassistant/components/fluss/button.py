"""Support for Fluss Devices."""

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussDataUpdateCoordinator
from .entity import FlussEntity

_LOGGER = logging.getLogger(__name__)

BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="trigger",
    name="Trigger",
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FlussDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fluss Devices, filtering out any invalid payloads."""
    coordinator = entry.runtime_data
    devices = coordinator.data.get("devices", [])

    entities: list[FlussButton] = []
    for device in devices:
        if not isinstance(device, dict):
            continue

        device_id = device.get("deviceId")
        if device_id is None:
            _LOGGER.debug("Skipping Fluss device without deviceId: %s", device)
            continue

        entities.append(FlussButton(coordinator, device_id, device))

    async_add_entities(entities)


class FlussButton(FlussEntity, ButtonEntity):
    """Representation of a Fluss button device."""

    def __init__(
        self, coordinator: FlussDataUpdateCoordinator, device_id: str, device: dict
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id, BUTTON_DESCRIPTION, device)
        self._attr_name = (
            self.device.get("deviceName", "Unknown Device")
            if self.device
            else "Unknown Device"
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.api.async_trigger_device(self.device_id)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success
