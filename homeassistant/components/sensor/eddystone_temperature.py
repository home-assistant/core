"""Read temperature information from Eddystone beacons.

Your beacons must be configured to transmit UID (for identification) and TLM
(for temperature) frames.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eddystone_temperature/

Original version of this code (for Skybeacons) by anpetrov.
https://github.com/anpetrov/skybeacon
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, TEMP_CELSIUS, STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP,
    CONF_NAMESPACE, CONF_INSTANCE, CONF_BT_DEVICE_ID, CONF_BEACONS)

REQUIREMENTS = ['beacontools[scan]==0.1.2']

_LOGGER = logging.getLogger(__name__)

BEACON_SCHEMA = vol.Schema({
    vol.Required(CONF_NAMESPACE): cv.string,
    vol.Required(CONF_INSTANCE): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BT_DEVICE_ID, default=0): cv.positive_int,
    vol.Required(CONF_BEACONS): vol.Schema({cv.string: BEACON_SCHEMA}),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Validate configuration, create devices and start monitoring thread."""
    _LOGGER.debug("Setting up...")

    bt_device_id = config.get("bt_device_id")

    beacons = config.get("beacons")
    devices = []

    for dev_name, properties in beacons.items():
        namespace = get_from_conf(properties, "namespace", 20)
        instance = get_from_conf(properties, "instance", 12)
        name = properties.get(CONF_NAME, dev_name)

        if instance is None or namespace is None:
            _LOGGER.error("Skipping %s", dev_name)
            continue
        else:
            devices.append(EddystoneTemp(name, namespace, instance))

    if len(devices) > 0:
        mon = Monitor(hass, devices, bt_device_id)

        def monitor_stop(_service_or_event):
            """Stop the monitor thread."""
            _LOGGER.info("Stopping scanner for eddystone beacons")
            mon.stop()

        add_devices(devices)
        mon.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
    else:
        _LOGGER.warning("No devices were added")


def get_from_conf(config, config_key, length):
    """Retrieve value from config and validate length."""
    string = config.get(config_key)
    if len(string) != length:
        _LOGGER.error("Error in config parameter \"%s\": Must be exactly %d "
                      "bytes. Device will not be added.",
                      config_key, length/2)
        return None
    else:
        return string


class EddystoneTemp(Entity):
    """Representation of a temperature sensor."""

    def __init__(self, name, namespace, instance):
        """Initialize a sensor."""
        self._name = name
        self.namespace = namespace
        self.instance = instance
        self.bt_addr = None
        self.temperature = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS


class Monitor(object):
    """Continously scan for BLE advertisements."""

    def __init__(self, hass, devices, bt_device_id):
        """Construct interface object."""
        self.hass = hass

        # list of beacons to monitor
        self.devices = devices
        # number of the bt device (hciX)
        self.bt_device_id = bt_device_id

        def callback(bt_addr, packet, additional_info):
            """Callback for new packets."""
            self.process_packet(additional_info['namespace'],
                                additional_info['instance'],
                                packet.temperature)

        # pylint: disable=import-error
        from beacontools import (BeaconScanner, EddystoneFilter,
                                 EddystoneTLMFrame)
        # Create a device filter for each device
        device_filters = [EddystoneFilter(d.namespace, d.instance)
                          for d in devices]

        self.scanner = BeaconScanner(callback, bt_device_id, device_filters,
                                     EddystoneTLMFrame)

    def start(self):
        """Continously scan for BLE advertisements."""
        self.scanner.start()

    def process_packet(self, namespace, instance, temperature):
        """Assign temperature to hass device."""
        _LOGGER.debug("Received temperature for <%s,%s>: %d",
                      namespace, instance, temperature)

        for dev in self.devices:
            if dev.namespace == namespace and dev.instance == instance:
                dev.temperature = temperature

    def stop(self):
        """Signal runner to stop and join thread."""
        _LOGGER.debug("Stopping...")
        self.scanner.stop()
        _LOGGER.debug("Stopped")
