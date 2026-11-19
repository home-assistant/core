"""Support for IRM KMI weather warnings."""

from datetime import datetime
from typing import Any, override

from irm_kmi_api import WarningData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import IrmKmiConfigEntry
from .entity import IrmKmiBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrmKmiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities([IrmKmiWarning(entry)])


def _is_active(warning: WarningData, now: datetime) -> bool:
    """Return whether the warning covers the given time."""
    return warning["starts_at"] <= now < warning["ends_at"]


class IrmKmiWarning(IrmKmiBaseEntity, BinarySensorEntity):
    """Weather warning binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "warning"
    _unrecorded_attributes = frozenset({"warnings"})

    def __init__(self, entry: IrmKmiConfigEntry) -> None:
        """Create a new instance of the warning sensor from a configuration entry."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.data[CONF_UNIQUE_ID]}-warning"

    @property
    @override
    def is_on(self) -> bool:
        """Return True if at least one warning is in effect right now."""
        now = dt_util.utcnow()
        return any(
            _is_active(warning, now) for warning in self.coordinator.data.warnings
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return every warning the provider published, active or not."""
        now = dt_util.utcnow()
        return {
            "warnings": [
                {**warning, "is_active": _is_active(warning, now)}
                for warning in self.coordinator.data.warnings
            ]
        }
