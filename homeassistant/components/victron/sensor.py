"""Support for Victron Venus sensors.

Light-weight platform file registering sensor entities. The actual entity
implementation is in this file; import of `Hub` is type-only to avoid a
runtime circular dependency with `hub.py`.
"""

from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .hub import Hub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Venus sensors from a config entry."""
    hub: Hub = config_entry.runtime_data
    hub.register_add_entities_callback(async_add_entities, MetricKind.SENSOR)


class VictronSensor(VictronBaseEntity, SensorEntity):
    """Implementation of a Victron Venus sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        simple_naming: bool,
        installation_id: str,
    ) -> None:
        """Initialize the sensor based on detauls in the metric."""
        self._attr_native_value = metric.value
        super().__init__(
            device, metric, device_info, "sensor", simple_naming, installation_id
        )

    def __repr__(self) -> str:
        """Return a string representation of the sensor."""
        return f"VictronSensor({super().__repr__()}, native_value={self._attr_native_value})"

    def _on_update_task(self, value: Any) -> None:
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.schedule_update_ha_state()
