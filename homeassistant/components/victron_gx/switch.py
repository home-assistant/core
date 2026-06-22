"""Support for Victron GX switches."""

from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricKind,
    WritableMetric as VictronVenusWritableMetric,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .binary_sensor import VictronBinarySensor
from .const import BINARY_SENSOR_OFF_ID, BINARY_SENSOR_ON_ID
from .entity import VictronBaseEntity
from .hub import VictronGxConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronGxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Victron GX switches from a config entry."""
    hub = config_entry.runtime_data

    def on_new_metric(
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Handle new switch metric discovery."""
        if TYPE_CHECKING:
            assert isinstance(metric, VictronVenusWritableMetric)
        async_add_entities(
            [VictronSwitch(device, metric, device_info, installation_id)]
        )

    hub.register_new_metric_callback(MetricKind.SWITCH, on_new_metric)


class VictronSwitch(VictronBaseEntity, SwitchEntity):
    """Implementation of a Victron GX switch."""

    def __init__(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusWritableMetric,
        device_info: DeviceInfo,
        installation_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, metric, device_info, installation_id)
        self._attr_is_on = VictronBinarySensor.convert_metric_value_to_is_on(
            metric.value
        )

    @callback
    def _on_update_cb(self, value: Any) -> None:
        self._attr_is_on = VictronBinarySensor.convert_metric_value_to_is_on(value)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if TYPE_CHECKING:
            assert isinstance(self._metric, VictronVenusWritableMetric)
        self._metric.set(BINARY_SENSOR_ON_ID)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if TYPE_CHECKING:
            assert isinstance(self._metric, VictronVenusWritableMetric)
        self._metric.set(BINARY_SENSOR_OFF_ID)
