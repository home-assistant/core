"""Read temperature information from Eddystone beacons.

Your beacons must be configured to transmit UID (for identification) and TLM
(for temperature) frames.
"""

from __future__ import annotations

import logging

from beacontools import BeaconScanner, EddystoneFilter, EddystoneTLMFrame
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_BEACONS = "beacons"
CONF_BT_DEVICE_ID = "bt_device_id"
CONF_INSTANCE = "instance"
CONF_NAMESPACE = "namespace"

BEACON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAMESPACE): cv.string,
        vol.Required(CONF_INSTANCE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_BT_DEVICE_ID, default=0): cv.positive_int,
        vol.Required(CONF_BEACONS): vol.Schema({cv.string: BEACON_SCHEMA}),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Validate configuration, create devices and start monitoring thread."""
    bt_device_id: int = config[CONF_BT_DEVICE_ID]

    beacons: dict[str, dict[str, str]] = config[CONF_BEACONS]
    devices: list[EddystoneTemp] = []

    for dev_name, properties in beacons.items():
        namespace = get_from_conf(properties, CONF_NAMESPACE, 20)
        instance = get_from_conf(properties, CONF_INSTANCE, 12)
        name = properties.get(CONF_NAME, dev_name)

        if instance is None or namespace is None:
            _LOGGER.error("Skipping %s", dev_name)
            continue

        devices.append(EddystoneTemp(name, namespace, instance))

    if devices:
        mon = Monitor(hass, devices, bt_device_id)

        def monitor_stop(event: Event) -> None:
            """Stop the monitor thread."""
            _LOGGER.debug("Stopping scanner for Eddystone beacons")
            mon.stop()

        def monitor_start(event: Event) -> None:
            """Start the monitor thread."""
            _LOGGER.debug("Starting scanner for Eddystone beacons")
            mon.start()

        add_entities(devices)
        mon.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, monitor_start)
    else:
        _LOGGER.warning("No devices were added")


def get_from_conf(config: dict[str, str], config_key: str, length: int) -> str | None:
    """Retrieve value from config and validate length."""
    string = config[config_key]
    if len(string) != length:
        _LOGGER.error(
            (
                "Error in configuration parameter %s: Must be exactly %d "
                "bytes. Device will not be added"
            ),
            config_key,
            length / 2,
        )
        return None
    return string


class EddystoneTemp(SensorEntity):
    """Representation of a temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_should_poll = False

    def __init__(self, name: str, namespace: str, instance: str) -> None:
        """Initialize a sensor."""
        self._attr_name = name
        self.namespace = namespace
        self.instance = instance
        self.bt_addr = None
        self.temperature = STATE_UNKNOWN

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.temperature


class Monitor:
    """Continuously scan for BLE advertisements."""

    def __init__(
        self, hass: HomeAssistant, devices: list[EddystoneTemp], bt_device_id: int
    ) -> None:
        """Construct interface object."""
        self.hass = hass

        # List of beacons to monitor
        self.devices = devices
        # Number of the bt device (hciX)
        self.bt_device_id = bt_device_id

        def callback(bt_addr, _, packet, additional_info):
            """Handle new packets."""
            self.process_packet(
                additional_info["namespace"],
                additional_info["instance"],
                packet.temperature,
            )

        device_filters = [EddystoneFilter(d.namespace, d.instance) for d in devices]

        self.scanner = BeaconScanner(
            callback, bt_device_id, device_filters, EddystoneTLMFrame
        )
        self.scanning = False

    def start(self) -> None:
        """Continuously scan for BLE advertisements."""
        if not self.scanning:
            self.scanner.start()
            self.scanning = True
        else:
            _LOGGER.debug("start() called, but scanner is already running")

    def process_packet(self, namespace, instance, temperature) -> None:
        """Assign temperature to device."""
        _LOGGER.debug(
            "Received temperature for <%s,%s>: %d", namespace, instance, temperature
        )

        for dev in self.devices:
            if (
                dev.namespace == namespace
                and dev.instance == instance
                and dev.temperature != temperature
            ):
                dev.temperature = temperature
                dev.schedule_update_ha_state()

    def stop(self) -> None:
        """Signal runner to stop and join thread."""
        if self.scanning:
            _LOGGER.debug("Stopping")
            self.scanner.stop()
            _LOGGER.debug("Stopped")
            self.scanning = False
        else:
            _LOGGER.debug("stop() called but scanner was not running")
