"""Main Hub class."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from victron_mqtt import (
    AuthenticationError,
    CannotConnectError,
    Device as VictronVenusDevice,
    Hub as VictronVenusHub,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricType,
    OperationMode,
    VictronEnum,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_INSTALLATION_ID, CONF_MODEL, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 30

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}

type VictronGxConfigEntry = ConfigEntry[Hub]

NewMetricCallback = Callable[
    [VictronVenusDevice, VictronVenusMetric, DeviceInfo, str], None
]


class Hub:
    """Victron MQTT Hub for managing communication and sensors."""

    def __init__(self, hass: HomeAssistant, entry: VictronGxConfigEntry) -> None:
        """Initialize Victron MQTT Hub.

        Args:
            hass: Home Assistant instance
            entry: ConfigEntry containing configuration

        """

        _LOGGER.debug(
            "Initializing hub. ConfigEntry: %s, data: %s",
            entry,
            async_redact_data({**entry.data, **entry.options}, TO_REDACT),
        )
        config = {**entry.data, **entry.options}
        self.hass = hass
        self.host = config[CONF_HOST]

        self._hub = VictronVenusHub(
            host=self.host,
            port=config.get(CONF_PORT, 1883),
            username=config.get(CONF_USERNAME) or None,
            password=config.get(CONF_PASSWORD) or None,
            use_ssl=config.get(CONF_SSL, False),
            installation_id=config.get(CONF_INSTALLATION_ID) or None,
            model_name=config.get(CONF_MODEL) or None,
            serial=config.get(CONF_SERIAL) or None,
            operation_mode=OperationMode.FULL,
            update_frequency_seconds=UPDATE_INTERVAL_SECONDS,
        )
        self._hub.on_new_metric = self._on_new_metric
        self.new_metric_callbacks: dict[MetricKind, NewMetricCallback] = {}

    async def start(self) -> None:
        """Start the Victron MQTT hub."""
        _LOGGER.info("Starting hub")
        try:
            await self._hub.connect()
        except AuthenticationError as auth_error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={"host": self.host},
            ) from auth_error
        except CannotConnectError as connect_error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.host},
            ) from connect_error

    async def stop(self) -> None:
        """Stop the Victron MQTT hub."""
        _LOGGER.info("Stopping hub")
        try:
            await self._hub.disconnect()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Ignoring error while disconnecting from hub %s during shutdown",
                self.host,
                exc_info=err,
            )

    def _on_new_metric(
        self,
        hub: VictronVenusHub,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
    ) -> None:
        _LOGGER.debug("New metric received. Device: %s, Metric: %s", device, metric)
        if TYPE_CHECKING:
            assert hub.installation_id is not None
        device_info = Hub._map_device_info(device, hub.installation_id)
        callback = self.new_metric_callbacks.get(metric.metric_kind)
        if callback is not None:
            callback(device, metric, device_info, hub.installation_id)

    @staticmethod
    def _map_device_info(
        device: VictronVenusDevice, installation_id: str
    ) -> DeviceInfo:
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{installation_id}_{device.unique_id}")},
            manufacturer=(
                device.manufacturer
                if device.manufacturer is not None
                else "Victron Energy"
            ),
            name=device.name,
            model=device.model,
            serial_number=device.serial_number,
        )
        # Don't set via_device for the GX device itself
        if device.unique_id != "system_0":
            device_info["via_device"] = (DOMAIN, f"{installation_id}_system_0")
        return device_info

    def is_device_connected(self, device_identifiers: set[tuple[str, str]]) -> bool:
        """Check if a device is currently known to the hub."""
        known_devices = self._hub.devices
        return any(
            identifier[1].removeprefix(f"{self._hub.installation_id}_") in known_devices
            for identifier in device_identifiers
            if identifier[0] == DOMAIN
        )

    def get_diagnostics_data(self) -> dict[str, Any]:
        """Return diagnostics data for the hub's device and entity tree."""
        return {
            device_id: {
                "name": device.name,
                "model": device.model,
                "manufacturer": device.manufacturer,
                "firmware_version": device.firmware_version,
                "device_type": device.device_type.string,
                "metrics": {
                    metric.short_id: {
                        "name": metric.name,
                        "value": "**REDACTED**"
                        if metric.metric_type == MetricType.LOCATION
                        else metric.value
                        if not isinstance(metric.value, VictronEnum)
                        else metric.value.id,
                        "unit": metric.unit_of_measurement,
                        "kind": metric.metric_kind.name,
                        "type": metric.metric_type.name,
                    }
                    for metric in device.metrics
                },
            }
            for device_id, device in self._hub.devices.items()
        }

    def register_new_metric_callback(
        self, kind: MetricKind, new_metric_callback: NewMetricCallback
    ) -> None:
        """Register a callback to handle a new specific metric kind."""
        _LOGGER.debug("Registering NewMetricCallback. kind: %s", kind)
        self.new_metric_callbacks[kind] = new_metric_callback

    def unregister_all_new_metric_callbacks(self) -> None:
        """Unregister all callbacks to handle new metrics for all metric kinds."""
        _LOGGER.debug("Unregistering NewMetricCallback")
        self.new_metric_callbacks.clear()
