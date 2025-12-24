"""Support for Victron Venus sensors.

Light-weight platform file registering sensor entities. The actual entity
implementation is in this file; import of `Hub` is type-only to avoid a
runtime circular dependency with `hub.py`.
"""

from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VictronGxConfigEntry
from .entity import VictronBaseEntity
from .hub import Hub

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Venus sensors from a config entry."""
    hub: Hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Handle new sensor metric discovery."""
        async_add_entities(
            [
                VictronSensor(
                    device,
                    metric,
                    device_info,
                )
            ]
        )

    hub.register_new_metric_callback(MetricKind.SENSOR, on_new_metric)


class VictronSensor(VictronBaseEntity, SensorEntity):
    """Implementation of a Victron Venus sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        self._attr_native_value = metric.value
        super().__init__(device, metric, device_info)

    @callback
    def _on_update_task(self, value: Any) -> None:
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.async_write_ha_state()
