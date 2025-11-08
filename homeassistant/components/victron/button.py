"""Support for Victron Venus buttons."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.button import ButtonEntity
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
    """Set up Victron Venus buttons from a config entry."""

    hub: Hub = config_entry.runtime_data
    hub.register_add_entities_callback(async_add_entities, MetricKind.BUTTON)


class VictronButton(VictronBaseEntity, ButtonEntity):
    """Implementation of a Victron Venus button using ButtonEntity."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        simple_naming: bool,
        installation_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            device, metric, device_info, "button", simple_naming, installation_id
        )

    def _on_update_task(self, value: Any) -> None:
        pass

    def press(self) -> None:
        """Press the button."""
        assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.info("Pressing button: %s", self._attr_unique_id)
        self._metric.set(SWITCH_ON)

    def __repr__(self) -> str:
        """Return a string representation of the sensor."""
        return f"VictronButton({super().__repr__()})"
