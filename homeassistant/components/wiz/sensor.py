"""Support for WiZ sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WizEntity
from .models import WizData

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rssi", name="RSSI", entity_registry_enabled_default=False
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wiz sensor."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WizSensor(wiz_data, entry.title, description) for description in SENSORS
    )


class WizSensor(WizEntity, SensorEntity):
    """Defines a WiZ sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self, wiz_data: WizData, name: str, description: SensorEntityDescription
    ) -> None:
        """Initialize an WiZ sensor."""
        super().__init__(wiz_data, name)
        self.entity_description = description
        self._attr_unique_id = f"{self._device.mac}_{description.key}"
        self._attr_name = f"{name} {description.name}"
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = self._device.state.pilotResult.get(
            self.entity_description.key
        )
