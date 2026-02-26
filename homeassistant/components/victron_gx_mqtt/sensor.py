"""Support for Victron Venus sensors.

Light-weight platform file registering sensor entities. The actual entity
implementation is in this file; import of `Hub` is type-only to avoid a
runtime circular dependency with `hub.py`.
"""

import logging
from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    FormulaMetric as VictronFormulaMetric,
    Metric as VictronVenusMetric,
    MetricKind,
)

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import Hub, VictronGxConfigEntry

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.

_LOGGER = logging.getLogger(__name__)


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


class VictronSensor(VictronBaseEntity, RestoreSensor):
    """Implementation of a Victron Venus sensor."""

    _baseline: float | None = None

    @callback
    def _on_update_task(self, value: Any) -> None:
        if self._baseline is not None:
            value += self._baseline
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore persistent state for FormulaMetric energy sensors."""

        # Only restore for:
        # 1. Total increasing sensors (like cumulative energy)
        # 2. FormulaMetrics (calculated values)
        should_restore = self.state_class in [
            SensorStateClass.TOTAL_INCREASING,
            SensorStateClass.TOTAL,
        ] and isinstance(self._metric, VictronFormulaMetric)
        self._attr_native_value = self._metric.value
        if not should_restore:
            # Call parent to register update callbacks
            await super().async_added_to_hass()
            return

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            assert isinstance(self._attr_native_value, (int, float)), (
                "sensor with stored baseline value must be numeric"
            )
            try:
                self._baseline = float(last_state.state)
                self._attr_native_value += self._baseline
                _LOGGER.debug(
                    "Restored baseline of %.3f for %s", self._baseline, self.entity_id
                )
            except ValueError:
                _LOGGER.warning(
                    "Could not restore state for %s: invalid value '%s'",
                    self.entity_id,
                    last_state.state,
                )
        # Call parent to register update callbacks
        await super().async_added_to_hass()
