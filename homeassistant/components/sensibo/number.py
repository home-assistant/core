"""Number platform for Sensibo integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class SensiboEntityDescriptionMixin:
    """Mixin values for Sensibo entities."""

    remote_key: str


@dataclass
class SensiboNumberEntityDescription(
    NumberEntityDescription, SensiboEntityDescriptionMixin
):
    """Class describing Sensibo Number entities."""


DEVICE_NUMBER_TYPES = (
    SensiboNumberEntityDescription(
        key="calibration_temp",
        remote_key="temperature",
        name="Temperature calibration",
        icon="mdi:thermometer",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.1,
    ),
    SensiboNumberEntityDescription(
        key="calibration_hum",
        remote_key="humidity",
        name="Humidity calibration",
        icon="mdi:water",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboNumber(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DEVICE_NUMBER_TYPES
    )


class SensiboNumber(SensiboDeviceBaseEntity, NumberEntity):
    """Representation of a Sensibo numbers."""

    entity_description: SensiboNumberEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboNumberEntityDescription,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the value from coordinator data."""
        value: float | None = getattr(self.device_data, self.entity_description.key)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set value for calibration."""
        data = {self.entity_description.remote_key: value}
        result = await self.async_send_command("set_calibration", {"data": data})
        if result["status"] == "success":
            setattr(self.device_data, self.entity_description.key, value)
            self.async_write_ha_state()
            return
        raise HomeAssistantError(f"Could not set calibration for device {self.name}")
