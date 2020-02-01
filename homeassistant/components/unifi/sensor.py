"""Support for bandwidth sensors with UniFi clients."""
import logging

from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import DISABLED_CONFIG_ENTRY

from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

ATTR_RECEIVING = "receiving"
ATTR_TRANSMITTING = "transmitting"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Sensor platform doesn't support configuration through configuration.yaml."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for UniFi integration."""
    controller = get_controller_from_config_entry(hass, config_entry)
    sensors = {}

    registry = await entity_registry.async_get_registry(hass)

    @callback
    def update_controller():
        """Update the values of the controller."""
        add_entities(controller, async_add_entities, sensors)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_update, update_controller)
    )

    @callback
    def update_disable_on_entities():
        """Update the values of the controller."""
        for entity in sensors.values():

            if entity.entity_registry_enabled_default == entity.enabled:
                continue

            disabled_by = None
            if not entity.entity_registry_enabled_default and entity.enabled:
                disabled_by = DISABLED_CONFIG_ENTRY

            registry.async_update_entity(
                entity.registry_entry.entity_id, disabled_by=disabled_by
            )

    controller.listeners.append(
        async_dispatcher_connect(
            hass, controller.signal_options_update, update_disable_on_entities
        )
    )

    update_controller()


@callback
def add_entities(controller, async_add_entities, sensors):
    """Add new sensor entities from the controller."""
    new_sensors = []

    for client_id in controller.api.clients:
        for direction, sensor_class in (
            ("rx", UniFiRxBandwidthSensor),
            ("tx", UniFiTxBandwidthSensor),
        ):
            item_id = f"{direction}-{client_id}"

            if item_id in sensors:
                continue

            sensors[item_id] = sensor_class(
                controller.api.clients[client_id], controller
            )
            new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors)


class UniFiRxBandwidthSensor(UniFiClient):
    """Receiving bandwidth sensor."""

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        if self.controller.option_allow_bandwidth_sensors:
            return True
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.is_wired:
            return self.client.wired_rx_bytes / 1000000
        return self.client.raw.get("rx_bytes", 0) / 1000000

    @property
    def name(self):
        """Return the name of the client."""
        name = self.client.name or self.client.hostname
        return f"{name} RX"

    @property
    def unique_id(self):
        """Return a unique identifier for this bandwidth sensor."""
        return f"rx-{self.client.mac}"


class UniFiTxBandwidthSensor(UniFiRxBandwidthSensor):
    """Transmitting bandwidth sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.is_wired:
            return self.client.wired_tx_bytes / 1000000
        return self.client.raw.get("tx_bytes", 0) / 1000000

    @property
    def name(self):
        """Return the name of the client."""
        name = self.client.name or self.client.hostname
        return f"{name} TX"

    @property
    def unique_id(self):
        """Return a unique identifier for this bandwidth sensor."""
        return f"tx-{self.client.mac}"
