"""Support for Victron GX button entities."""

import logging
from typing import Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_ON_ID
from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # There is no I/O in the entity itself.


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX button entities from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new button metric discovery."""
        assert isinstance(metric, VictronVenusWritableMetric)
        async_add_entities(
            [VictronButton(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.BUTTON, on_new_metric)


class VictronButton(VictronBaseEntity, ButtonEntity):
    """Implementation of a Victron GX button entity."""

    @callback
    def _on_update_cb(self, value: Any) -> None:
        pass

    def press(self) -> None:
        """Press the button."""
        assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.debug("Pressing button: %s", self._attr_unique_id)
        self._metric.set(SWITCH_ON_ID)
