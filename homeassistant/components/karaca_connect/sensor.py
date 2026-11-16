"""Sensor support for Karaca Connect."""

from typing import override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaracaConfigEntry
from .const import CONF_DEVICE_ID
from .entity import KaracaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KaracaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the read-only status sensor."""
    async_add_entities([KaracaStatusSensor(entry)])


class KaracaStatusSensor(KaracaEntity, SensorEntity):
    """Expose the mode returned by the Karaca cloud."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:kettle-steam"

    def __init__(self, entry: KaracaConfigEntry) -> None:
        """Initialize the cloud status sensor."""
        super().__init__(entry.runtime_data.coordinator, entry)
        self._attr_unique_id = f"{entry.data[CONF_DEVICE_ID]}_status"

    @property
    @override
    def native_value(self) -> str | None:
        """Return the mode label as reported by the API."""
        detail = self.coordinator.data.get("detail", {})
        if not isinstance(detail, dict):
            return None
        if str(detail.get("mode")) == "1":
            return "standby"
        label = detail.get("modeStateLabel") or detail.get("modeName")
        return str(label) if label is not None else None
