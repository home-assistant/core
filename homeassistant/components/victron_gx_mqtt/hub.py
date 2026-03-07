"""Main Hub class."""

from collections.abc import Callable
import logging

from victron_mqtt import (
    AuthenticationError,
    CannotConnectError,
    Device as VictronVenusDevice,
    Hub as VictronVenusHub,
    Metric as VictronVenusMetric,
    MetricKind,
    OperationMode,
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

from .const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}

type VictronGxConfigEntry = ConfigEntry[Hub]

NewMetricCallback = Callable[[VictronVenusDevice, VictronVenusMetric, DeviceInfo], None]


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
        self.id = entry.unique_id

        self._hub = VictronVenusHub(
            host=self.host,
            port=config.get(CONF_PORT, 1883),
            username=config.get(CONF_USERNAME) or None,
            password=config.get(CONF_PASSWORD) or None,
            use_ssl=config.get(CONF_SSL, False),
            installation_id=config.get(CONF_INSTALLATION_ID) or None,
            model_name=config.get(CONF_MODEL) or None,
            serial=config.get(CONF_SERIAL, "noserial"),
            topic_prefix=config.get(CONF_ROOT_TOPIC_PREFIX) or None,
            operation_mode=OperationMode.READ_ONLY,
            update_frequency_seconds=config.get(
                CONF_UPDATE_FREQUENCY_SECONDS, DEFAULT_UPDATE_FREQUENCY_SECONDS
            ),
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
                f"Authentication failed for {self.host}: {auth_error}"
            ) from auth_error
        except CannotConnectError as connect_error:
            raise ConfigEntryNotReady(
                f"Cannot connect to the hub: {connect_error}"
            ) from connect_error

    async def stop(self) -> None:
        """Stop the Victron MQTT hub."""
        _LOGGER.info("Stopping hub")
        await self._hub.disconnect()

    def _on_new_metric(
        self,
        hub: VictronVenusHub,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
    ) -> None:
        _LOGGER.debug("New metric received. Device: %s, Metric: %s", device, metric)
        assert hub.installation_id is not None
        device_info = Hub._map_device_info(device, hub.installation_id)
        callback = self.new_metric_callbacks.get(metric.metric_kind)
        if callback is not None:
            callback(device, metric, device_info)

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
            name=(
                f"{device.name} (ID: {device.device_id})"
                if device.device_id != "0"
                else device.name
            ),
            model=device.model,
            serial_number=device.serial_number,
        )
        # Don't set via_device for the GX device itself
        if device.unique_id != "system_0":
            device_info["via_device"] = (DOMAIN, f"{installation_id}_system_0")
        return device_info

    def register_new_metric_callback(
        self, kind: MetricKind, new_metric_callback: NewMetricCallback
    ) -> None:
        """Register a callback to handle a new specific metric kind."""
        _LOGGER.debug("Registering NewMetricCallback. kind: %s", kind)
        assert kind not in self.new_metric_callbacks, (
            f"NewMetricCallback for kind {kind} is already registered"
        )
        self.new_metric_callbacks[kind] = new_metric_callback

    def unregister_all_new_metric_callbacks(self) -> None:
        """Unregister all callbacks to handle new metrics for all metric kinds."""
        _LOGGER.debug("Unregistering NewMetricCallback")
        self.new_metric_callbacks.clear()
