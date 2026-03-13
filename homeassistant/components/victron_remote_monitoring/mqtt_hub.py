"""MQTT hub adapter for Victron Remote Monitoring."""

from __future__ import annotations

from collections.abc import Callable
import logging

from victron_mqtt import (
    Device as VictronDevice,
    Hub as VictronMQTTHub,
    Metric as VictronMetric,
    MetricKind,
)

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NewMetricCallback = Callable[[VictronDevice, VictronMetric, DeviceInfo, int], None]


class VRMMqttHub:
    """Adapter to handle MQTT metrics and Home Assistant callbacks."""

    def __init__(self, site_id: int) -> None:
        """Initialize the adapter."""
        self._site_id = site_id
        self._hub: VictronMQTTHub | None = None
        self._callbacks: dict[MetricKind, NewMetricCallback] = {}

    def attach(self, hub: VictronMQTTHub) -> None:
        """Attach the underlying Victron MQTT hub."""
        self._hub = hub
        self._hub.on_new_metric = self._on_new_metric

    def detach(self) -> None:
        """Detach the underlying Victron MQTT hub."""
        if self._hub is not None:
            self._hub.on_new_metric = None
        self._hub = None

    def register_new_metric_callback(
        self, kind: MetricKind, callback: NewMetricCallback
    ) -> None:
        """Register a callback for a metric kind."""
        if kind in self._callbacks:
            _LOGGER.debug("Metric callback already registered: %s", kind)
            return
        self._callbacks[kind] = callback

    def unregister_all_new_metric_callbacks(self) -> None:
        """Remove all metric callbacks."""
        self._callbacks.clear()

    def _on_new_metric(
        self,
        hub: VictronMQTTHub,
        device: VictronDevice,
        metric: VictronMetric,
    ) -> None:
        """Handle new metric discovery from the MQTT hub."""
        _LOGGER.debug("New MQTT metric discovered: %s", metric)
        device_info = self._map_device_info(device)
        callback = self._callbacks.get(metric.metric_kind)
        if callback is not None:
            callback(device, metric, device_info, self._site_id)

    def _map_device_info(self, device: VictronDevice) -> DeviceInfo:
        """Create Home Assistant device info for a Victron device."""
        name = device.name
        if device.device_id != "0":
            name = f"{name} (ID: {device.device_id})"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._site_id}_{device.unique_id}")},
            manufacturer=device.manufacturer or "Victron Energy",
            model=device.model,
            name=name,
            serial_number=device.serial_number,
        )
