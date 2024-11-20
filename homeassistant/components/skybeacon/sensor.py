"""Support for Skybeacon temperature/humidity Bluetooth LE sensors."""

from __future__ import annotations

import logging
import threading
from uuid import UUID

from pygatt import BLEAddressType
from pygatt.backends import Characteristic, GATTToolBackend
from pygatt.exceptions import BLEError, NotConnectedError, NotificationTimeout
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device"
ATTR_MODEL = "model"

BLE_TEMP_HANDLE = 0x24
BLE_TEMP_UUID = "0000ff92-0000-1000-8000-00805f9b34fb"

CONNECT_LOCK = threading.Lock()
CONNECT_TIMEOUT = 30

DEFAULT_NAME = "Skybeacon"

SKIP_HANDLE_LOOKUP = True

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Skybeacon sensor."""
    name = config.get(CONF_NAME)
    mac = config.get(CONF_MAC)
    _LOGGER.debug("Setting up")

    mon = Monitor(hass, mac, name)
    add_entities([SkybeaconTemp(name, mon)])
    add_entities([SkybeaconHumid(name, mon)])

    def monitor_stop(_service_or_event):
        """Stop the monitor thread."""
        _LOGGER.debug("Stopping monitor for %s", name)
        mon.terminate()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
    mon.start()


class SkybeaconHumid(SensorEntity):
    """Representation of a Skybeacon humidity sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, name, mon):
        """Initialize a sensor."""
        self.mon = mon
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.mon.data["humid"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_DEVICE: "SKYBEACON", ATTR_MODEL: 1}


class SkybeaconTemp(SensorEntity):
    """Representation of a Skybeacon temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, name, mon):
        """Initialize a sensor."""
        self.mon = mon
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.mon.data["temp"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_DEVICE: "SKYBEACON", ATTR_MODEL: 1}


class Monitor(threading.Thread, SensorEntity):
    """Connection handling."""

    def __init__(self, hass, mac, name):
        """Construct interface object."""
        threading.Thread.__init__(self)
        self.daemon = False
        self.hass = hass
        self.mac = mac
        self.name = name
        self.data = {"temp": STATE_UNKNOWN, "humid": STATE_UNKNOWN}
        self.keep_going = True
        self.event = threading.Event()

    def run(self):
        """Thread that keeps connection alive."""
        cached_char = Characteristic(BLE_TEMP_UUID, BLE_TEMP_HANDLE)
        adapter = GATTToolBackend()
        while True:
            try:
                _LOGGER.debug("Connecting to %s", self.name)
                # We need concurrent connect, so lets not reset the device
                adapter.start(reset_on_start=False)
                # Seems only one connection can be initiated at a time
                with CONNECT_LOCK:
                    device = adapter.connect(
                        self.mac, CONNECT_TIMEOUT, BLEAddressType.random
                    )
                if SKIP_HANDLE_LOOKUP:
                    # HACK: inject handle mapping collected offline
                    device._characteristics[UUID(BLE_TEMP_UUID)] = cached_char  # noqa: SLF001
                # Magic: writing this makes device happy
                device.char_write_handle(0x1B, bytearray([255]), False)
                device.subscribe(BLE_TEMP_UUID, self._update)
                _LOGGER.debug("Subscribed to %s", self.name)
                while self.keep_going:
                    # protect against stale connections, just read temperature
                    device.char_read(BLE_TEMP_UUID, timeout=CONNECT_TIMEOUT)
                    self.event.wait(60)
                break
            except (BLEError, NotConnectedError, NotificationTimeout) as ex:
                _LOGGER.error("Exception: %s ", str(ex))
            finally:
                adapter.stop()

    def _update(self, handle, value):
        """Notification callback from pygatt."""
        _LOGGER.debug(
            "%s: %15s temperature = %-2d.%-2d, humidity = %3d",
            handle,
            self.name,
            value[0],
            value[2],
            value[1],
        )
        self.data["temp"] = float(f"{value[0]}.{value[2]}")
        self.data["humid"] = value[1]

    def terminate(self):
        """Signal runner to stop and join thread."""
        self.keep_going = False
        self.event.set()
        self.join()
