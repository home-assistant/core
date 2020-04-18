"""Support for bandwidth sensors with UniFi clients."""
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.const import DATA_MEGABYTES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

RX_SENSOR = "rx"
TX_SENSOR = "tx"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Sensor platform doesn't support configuration through configuration.yaml."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for UniFi integration."""
    controller = get_controller_from_config_entry(hass, config_entry)
    controller.entities[DOMAIN] = {RX_SENSOR: set(), TX_SENSOR: set()}

    option_allow_bandwidth_sensors = controller.option_allow_bandwidth_sensors

    @callback
    def items_added():
        """Update the values of the controller."""
        if not controller.option_allow_bandwidth_sensors:
            return

        add_entities(controller, async_add_entities)

    controller.listeners.append(
        async_dispatcher_connect(hass, controller.signal_update, items_added)
    )

    @callback
    def options_updated():
        """Update the values of the controller."""
        nonlocal option_allow_bandwidth_sensors

        if option_allow_bandwidth_sensors != controller.option_allow_bandwidth_sensors:
            option_allow_bandwidth_sensors = controller.option_allow_bandwidth_sensors

            if option_allow_bandwidth_sensors:
                items_added()

    controller.listeners.append(
        async_dispatcher_connect(
            hass, controller.signal_options_update, options_updated
        )
    )

    items_added()


@callback
def add_entities(controller, async_add_entities):
    """Add new sensor entities from the controller."""
    sensors = []

    for client_id in controller.api.clients:
        for sensor_class in (UniFiRxBandwidthSensor, UniFiTxBandwidthSensor):
            if client_id in controller.entities[DOMAIN][sensor_class.TYPE]:
                continue
            sensors.append(sensor_class(controller.api.clients[client_id], controller))

    if sensors:
        async_add_entities(sensors)


class UniFiBandwidthSensor(UniFiClient):
    """UniFi bandwidth sensor base class."""

    TYPE = ""

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.upper()}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this bandwidth sensor."""
        return f"{self.TYPE}-{self.client.mac}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return DATA_MEGABYTES

    async def async_added_to_hass(self) -> None:
        """Client entity created."""
        await super().async_added_to_hass()
        self.controller.entities[DOMAIN][self.TYPE].add(self.client.mac)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_options_update, self.options_updated
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_remove, self.remove_item
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect client object when removed."""
        await super().async_will_remove_from_hass()
        self.controller.entities[DOMAIN][self.TYPE].remove(self.client.mac)

    @callback
    def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_bandwidth_sensors:
            self.hass.async_create_task(self.async_remove())

    @callback
    def remove_item(self, mac_addresses: set) -> None:
        """Remove entity if client MAC is part of set."""
        if self.client.mac in mac_addresses:
            self.hass.async_create_task(self.async_remove())


class UniFiRxBandwidthSensor(UniFiBandwidthSensor):
    """Receiving bandwidth sensor."""

    TYPE = RX_SENSOR

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_rx_bytes / 1000000
        return self.client.rx_bytes / 1000000


class UniFiTxBandwidthSensor(UniFiBandwidthSensor):
    """Transmitting bandwidth sensor."""

    TYPE = TX_SENSOR

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_tx_bytes / 1000000
        return self.client.tx_bytes / 1000000
