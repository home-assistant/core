"""Binary sensors for GeoSphere Austria weather warnings."""

from dataclasses import dataclass
from typing import Any

from pygeosphere_warnings import WarningType, WeatherWarning

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import GeoSphereConfigEntry, GeoSphereUpdateCoordinator
from .entity import GeoSphereEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GeoSphereWarningBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor for a GeoSphere warning type."""

    warning_type: WarningType


WARNING_SENSORS: tuple[GeoSphereWarningBinarySensorDescription, ...] = tuple(
    GeoSphereWarningBinarySensorDescription(
        key=f"{warning_type.name.lower()}_warning",
        translation_key=f"{warning_type.name.lower()}_warning",
        warning_type=warning_type,
        device_class=BinarySensorDeviceClass.SAFETY,
    )
    for warning_type in WarningType
)

AUTO_THUNDERSTORM_SENSOR = BinarySensorEntityDescription(
    key="auto_thunderstorm_warning",
    translation_key="auto_thunderstorm_warning",
    device_class=BinarySensorDeviceClass.SAFETY,
    entity_registry_enabled_default=False,
)


def _warning_attributes(warning: WeatherWarning) -> dict[str, Any]:
    """Return the attributes describing a single warning."""
    return {
        "level": warning.level.name.lower(),
        "start": warning.start.isoformat(),
        "end": warning.end.isoformat(),
        "text": warning.text,
        "impacts": warning.impacts,
        "recommendations": warning.recommendations,
        "meteo_text": warning.meteo_text,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoSphereConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                GeoSphereWarningBinarySensor(coordinator, description)
                for description in WARNING_SENSORS
            ),
            GeoSphereThunderstormBinarySensor(coordinator, AUTO_THUNDERSTORM_SENSOR),
        ]
    )


class GeoSphereWarningBinarySensor(GeoSphereEntity, BinarySensorEntity):
    """Binary sensor that is on while a warning of its type is active."""

    entity_description: GeoSphereWarningBinarySensorDescription

    def __init__(
        self,
        coordinator: GeoSphereUpdateCoordinator,
        description: GeoSphereWarningBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description)
        self._warnings = self._current_warnings()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the cached warnings when the coordinator updates."""
        self._warnings = self._current_warnings()
        super()._handle_coordinator_update()

    def _current_warnings(self) -> list[WeatherWarning]:
        """Return all warnings of this sensor's type, including upcoming ones."""
        return sorted(
            (
                warning
                for warning in self.coordinator.data.location_warnings.warnings
                if warning.warning_type == self.entity_description.warning_type
            ),
            key=lambda warning: warning.start,
        )

    @property
    def is_on(self) -> bool:
        """Return True if a warning of this type is currently active."""
        now = dt_util.utcnow()
        return any(warning.is_active(now) for warning in self._warnings)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the current and upcoming warnings."""
        now = dt_util.utcnow()
        warnings = self._warnings
        attributes: dict[str, Any] = {
            "warnings": [_warning_attributes(warning) for warning in warnings]
        }
        if active := [warning for warning in warnings if warning.is_active(now)]:
            attributes |= _warning_attributes(max(active, key=lambda w: w.level))
        return attributes


class GeoSphereThunderstormBinarySensor(GeoSphereEntity, BinarySensorEntity):
    """Binary sensor for the automated thunderstorm warnings."""

    @property
    def is_on(self) -> bool:
        """Return True if an automated thunderstorm warning is active."""
        return self.coordinator.data.thunderstorm_intensity > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the thunderstorm intensity."""
        return {"intensity": self.coordinator.data.thunderstorm_intensity}
