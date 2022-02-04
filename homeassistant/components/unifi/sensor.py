"""Sensor platform for UniFi Network integration.

Support for bandwidth sensors of network clients.
Support for uptime sensors of network clients.
"""
from datetime import datetime, timedelta

from homeassistant.components.sensor import DOMAIN, SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_MEGABYTES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .unifi_client import UniFiClient

RX_SENSOR = "rx"
TX_SENSOR = "tx"
UPTIME_SENSOR = "uptime"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Network integration."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {
        RX_SENSOR: set(),
        TX_SENSOR: set(),
        UPTIME_SENSOR: set(),
    }

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_allow_bandwidth_sensors:
            add_bandwidth_entities(controller, async_add_entities, clients)

        if controller.option_allow_uptime_sensors:
            add_uptime_entities(controller, async_add_entities, clients)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()


@callback
def add_bandwidth_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        for sensor_class in (UniFiRxBandwidthSensor, UniFiTxBandwidthSensor):
            if mac in controller.entities[DOMAIN][sensor_class.TYPE]:
                continue

            client = controller.api.clients[mac]
            sensors.append(sensor_class(client, controller))

    if sensors:
        async_add_entities(sensors)


@callback
def add_uptime_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        if mac in controller.entities[DOMAIN][UniFiUpTimeSensor.TYPE]:
            continue

        client = controller.api.clients[mac]
        sensors.append(UniFiUpTimeSensor(client, controller))

    if sensors:
        async_add_entities(sensors)


class UniFiBandwidthSensor(UniFiClient, SensorEntity):
    """UniFi Network bandwidth sensor base class."""

    DOMAIN = DOMAIN

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = DATA_MEGABYTES

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.upper()}"

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_bandwidth_sensors:
            await self.remove_item({self.client.mac})


class UniFiRxBandwidthSensor(UniFiBandwidthSensor):
    """Receiving bandwidth sensor."""

    TYPE = RX_SENSOR

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_rx_bytes_r / 1000000
        return self.client.rx_bytes_r / 1000000


class UniFiTxBandwidthSensor(UniFiBandwidthSensor):
    """Transmitting bandwidth sensor."""

    TYPE = TX_SENSOR

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_tx_bytes_r / 1000000
        return self.client.tx_bytes_r / 1000000


class UniFiUpTimeSensor(UniFiClient, SensorEntity):
    """UniFi Network client uptime sensor."""

    DOMAIN = DOMAIN
    TYPE = UPTIME_SENSOR

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.last_updated_time = self.client.uptime

    @callback
    def async_update_callback(self) -> None:
        """Update sensor when time has changed significantly.

        This will help avoid unnecessary updates to the state machine.
        """
        update_state = True

        if self.client.uptime < 1000000000:
            if self.client.uptime > self.last_updated_time:
                update_state = False
        else:
            if self.client.uptime <= self.last_updated_time:
                update_state = False

        self.last_updated_time = self.client.uptime

        if not update_state:
            return

        super().async_update_callback()

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.capitalize()}"

    @property
    def native_value(self) -> datetime:
        """Return the uptime of the client."""
        if self.client.uptime < 1000000000:
            return dt_util.now() - timedelta(seconds=self.client.uptime)
        return dt_util.utc_from_timestamp(float(self.client.uptime))

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_uptime_sensors:
            await self.remove_item({self.client.mac})
