"""Support for Victron GX select entities."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    VictronEnum,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.select import SelectEntity
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
    """Set up Victron GX select entities from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new select metric discovery."""
        assert isinstance(metric, VictronVenusWritableMetric)
        async_add_entities(
            [VictronSelect(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.SELECT, on_new_metric)


class VictronSelect(VictronBaseEntity, SelectEntity):
    """Implementation of a Victron GX select entity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(device, metric, device_info, installation_id)
        if TYPE_CHECKING:
            assert metric.enum_values, "Select metric will always have enum values"
        self._attr_options = metric.enum_values
        self._attr_current_option = VictronSelect._normalize_value(metric.value)

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_current_option = VictronSelect._normalize_value(value)
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if TYPE_CHECKING:
            assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.debug("Setting select %s to %s", self._attr_unique_id, option)
        self._metric.set(option)

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize Victron enum values to their enum code."""
        return value.id if isinstance(value, VictronEnum) else value
