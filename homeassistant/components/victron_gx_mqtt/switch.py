"""Support for Victron Venus switches with 4 states."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_OFF, SWITCH_ON
from .entity import VictronBaseEntity

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron Venus switches from a config entry."""

    hub: Hub = config_entry.runtime_data
    hub.register_add_entities_callback(async_add_entities, MetricKind.SWITCH)


class VictronSwitch(VictronBaseEntity, SwitchEntity):
    """Implementation of a Victron Venus multiple state select using SelectEntity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        writable_metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        simple_naming: bool,
        installation_id: str,
    ) -> None:
        """Initialize the switch."""
        self._attr_is_on = str(writable_metric.value) == SWITCH_ON
        super().__init__(
            device,
            writable_metric,
            device_info,
            "switch",
            simple_naming,
            installation_id,
        )

    def __repr__(self) -> str:
        """Return a string representation of the sensor."""
        return f"VictronSwitch({super().__repr__()}, is_on={self._attr_is_on})"

    def _on_update_task(self, value: Any) -> None:
        new_val = str(value) == SWITCH_ON
        if self._attr_is_on == new_val:
            return
        self._attr_is_on = new_val
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.info("Turning on switch: %s", self._attr_unique_id)
        self._metric.set(SWITCH_ON)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.info("Turning off switch: %s", self._attr_unique_id)
        self._metric.set(SWITCH_OFF)
