"""Support for Victron Venus binary sensors."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
)

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_ON
from .entity import VictronBaseEntity

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Venus binary sensors from a config entry."""

    hub: Hub = config_entry.runtime_data
    hub.register_add_entities_callback(async_add_entities, MetricKind.BINARY_SENSOR)


class VictronBinarySensor(VictronBaseEntity, BinarySensorEntity):
    """Implementation of a Victron Venus binary sensor."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        simple_naming: bool,
        installation_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        self._attr_is_on = bool(metric.value)
        super().__init__(
            device, metric, device_info, "binary_sensor", simple_naming, installation_id
        )

    def __repr__(self) -> str:
        """Return a string representation of the sensor."""
        return f"VictronBinarySensor({super().__repr__()}), is_on={self._attr_is_on})"

    def _on_update_task(self, value: Any) -> None:
        new_val = str(value) == SWITCH_ON
        if self._attr_is_on == new_val:
            return
        self._attr_is_on = new_val
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return the current state of the binary sensor."""
        assert self._attr_is_on is not None
        return self._attr_is_on
