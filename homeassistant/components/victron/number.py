"""Support for Victron Venus number entities."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Venus numbers from a config entry."""

    hub: Hub = config_entry.runtime_data
    hub.register_add_entities_callback(async_add_entities, MetricKind.NUMBER)


class VictronNumber(VictronBaseEntity, NumberEntity):
    """Implementation of a Victron Venus number entity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        writable_metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        simple_naming: bool,
        installation_id: str,
    ) -> None:
        """Initialize the number entity."""
        self._attr_native_value = writable_metric.value
        if isinstance(writable_metric.min_value, int | float):
            self._attr_native_min_value = writable_metric.min_value
        if isinstance(writable_metric.max_value, int | float):
            self._attr_native_max_value = writable_metric.max_value
        if isinstance(writable_metric.step, int | float):
            self._attr_native_step = writable_metric.step
        super().__init__(
            device,
            writable_metric,
            device_info,
            "number",
            simple_naming,
            installation_id,
        )

    def __repr__(self) -> str:
        """Return a string representation of the sensor."""
        return f"VictronNumber({super().__repr__()}, native_value={self._attr_native_value})"

    def _on_update_task(self, value: Any) -> None:
        if self._attr_native_value == value:
            return
        self._attr_native_value = value
        self.schedule_update_ha_state()

    @property
    def native_value(self):
        """Return the current value."""
        return self._metric.value

    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.info("Setting number %s on switch: %s", value, self._attr_unique_id)
        self._metric.set(value)
