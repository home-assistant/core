"""Main Hub class."""

import logging

from victron_mqtt import (
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
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor import VictronBinarySensor
from .const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_SIMPLE_NAMING,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)
from .entity import VictronBaseEntity
from .sensor import VictronSensor

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Victron MQTT Hub for managing communication and sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Victron MQTT Hub.

        Args:
            hass: Home Assistant instance
            entry: ConfigEntry containing configuration

        """

        _LOGGER.info("Initializing hub. ConfigEntry: %s, data: %s", entry, entry.data)
        self.hass = hass
        self.entry = entry
        self.id = entry.unique_id

        config = entry.data
        self.simple_naming = config.get(CONF_SIMPLE_NAMING, False)
        host = config.get(CONF_HOST)
        assert host is not None

        self._hub: VictronVenusHub = VictronVenusHub(
            host=host,
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
        self.add_entities_map: dict[MetricKind, AddEntitiesCallback] = {}

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)

    async def start(self):
        """Start the Victron MQTT hub."""
        _LOGGER.info("Starting hub")
        try:
            await self._hub.connect()
        except CannotConnectError as connect_error:
            raise ConfigEntryNotReady(
                f"Cannot connect to the hub: {connect_error}"
            ) from connect_error

    async def stop(self, event: Event | None = None):
        """Stop the Victron MQTT hub."""
        _LOGGER.info("Stopping hub")
        await self._hub.disconnect()

    def _on_new_metric(
        self,
        hub: VictronVenusHub,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
    ):
        _LOGGER.info("New metric received. Device: %s, Metric: %s", device, metric)
        assert hub.installation_id is not None
        device_info = Hub._map_device_info(device, hub.installation_id)
        entity = self.create_entity(device, metric, device_info, hub.installation_id)

        # Add entity dynamically to the platform
        self.add_entities_map[metric.metric_kind]([entity])

    @staticmethod
    def _map_device_info(
        device: VictronVenusDevice, installation_id: str
    ) -> DeviceInfo:
        info: DeviceInfo = {}
        info["identifiers"] = {(DOMAIN, f"{installation_id}_{device.unique_id}")}
        info["manufacturer"] = (
            device.manufacturer if device.manufacturer is not None else "Victron Energy"
        )
        info["name"] = (
            f"{device.name} (ID: {device.device_id})"
            if device.device_id != "0"
            else device.name
        )
        info["model"] = device.model
        info["serial_number"] = device.serial_number

        return info

    def register_add_entities_callback(
        self, async_add_entities: AddEntitiesCallback, kind: MetricKind
    ):
        """Register a callback to add entities for a specific metric kind."""
        _LOGGER.info(
            "Registering AddEntitiesCallback. kind: %s, AddEntitiesCallback: %s",
            kind,
            async_add_entities,
        )
        self.add_entities_map[kind] = async_add_entities

    def create_entity(
        self,
        device: VictronVenusDevice,
        metric: VictronVenusMetric,
        info: DeviceInfo,
        installation_id: str,
    ) -> VictronBaseEntity:
        """Create a VictronBaseEntity from a device and metric."""
        if metric.metric_kind == MetricKind.SENSOR:
            return VictronSensor(
                device, metric, info, self.simple_naming, installation_id
            )
        if metric.metric_kind == MetricKind.BINARY_SENSOR:
            return VictronBinarySensor(
                device, metric, info, self.simple_naming, installation_id
            )
        raise ValueError(f"Unsupported metric kind: {metric.metric_kind}")

    def publish(
        self, metric_id: str, device_id: str, value: str | float | None
    ) -> None:
        """Publish a message to the Victron MQTT hub."""
        _LOGGER.info(
            "Publish service called with: metric_id=%s, device_id=%s, value=%s",
            metric_id,
            device_id,
            value,
        )
        self._hub.publish(metric_id, device_id, value)
