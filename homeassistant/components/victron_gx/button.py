"""Support for Victron GX button entities."""

import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    GenericOnOff,
    Metric as VictronVenusMetric,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
        if TYPE_CHECKING:
            assert isinstance(metric, VictronVenusWritableMetric)
        async_add_entities(
            [VictronButton(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.BUTTON, on_new_metric)


class VictronButton(VictronBaseEntity, ButtonEntity):
    """Implementation of a Victron GX button entity."""

    @callback
    def _on_update_cb(self, _value: Any) -> None:
        # Buttons are stateless in HA; incoming metric
        # updates are intentionally ignored.
        pass

    async def async_press(self) -> None:
        """Press the button."""
        if TYPE_CHECKING:
            assert isinstance(self._metric, VictronVenusWritableMetric)
        _LOGGER.debug("Pressing button: %s", self.unique_id)
        self._metric.set(GenericOnOff.ON)
