"""Support for Victron GX time entities."""

from datetime import time
import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX time entities from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new time metric discovery."""
        if TYPE_CHECKING:
            assert isinstance(metric, VictronVenusWritableMetric)
        async_add_entities([VictronTime(device, metric, device_info, installation_id)])

    hub.register_new_metric_callback(MetricKind.TIME, on_new_metric)


class VictronTime(VictronBaseEntity, TimeEntity):
    """Implementation of a Victron GX time entity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(device, metric, device_info, installation_id)
        self._attr_native_value = VictronTime.victron_time_to_time(metric.value)

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_native_value = VictronTime.victron_time_to_time(value)
        self.async_write_ha_state()

    async def async_set_value(self, value: time) -> None:
        """Set a new time value."""
        if TYPE_CHECKING:
            assert isinstance(self._metric, VictronVenusWritableMetric)
        total_minutes = VictronTime.time_to_victron_time(value)
        _LOGGER.debug(
            "Setting time %s (%d minutes) on entity: %s",
            value,
            total_minutes,
            self._attr_unique_id,
        )
        self._metric.set(total_minutes)

    @staticmethod
    def victron_time_to_time(value: int | None) -> time | None:
        """Convert minutes since midnight to time object."""
        if value is None:
            return None
        total_minutes = int(value)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return time(hour=hours, minute=minutes)

    @staticmethod
    def time_to_victron_time(value: time) -> int:
        """Convert time object to minutes since midnight."""
        return value.hour * 60 + value.minute
