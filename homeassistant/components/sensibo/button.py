"""Button platform for Sensibo integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0

DEVICE_BUTTON_TYPES: ButtonEntityDescription = ButtonEntityDescription(
    key="reset_filter",
    name="Reset filter",
    icon="mdi:air-filter",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboDeviceButton] = []

    entities.extend(
        SensiboDeviceButton(coordinator, device_id, DEVICE_BUTTON_TYPES)
        for device_id, device_data in coordinator.data.parsed.items()
    )

    async_add_entities(entities)


class SensiboDeviceButton(SensiboDeviceBaseEntity, ButtonEntity):
    """Representation of a Sensibo Device Binary Sensor."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: ButtonEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Button."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        result = await self.async_send_command("reset_filter")
        if result["status"] == "success":
            await self.coordinator.async_request_refresh()
            return
        raise HomeAssistantError(f"Could not set calibration for device {self.name}")
