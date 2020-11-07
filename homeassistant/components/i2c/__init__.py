"""Support for I2C bus."""
import logging
import threading
import time

import smbus2
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_I2CBUS = "bus"
CONF_SCAN_PERIOD = "scan_interval"

DEFAULT_I2CBUS = 1
DEFAULT_SCAN_PERIOD = 100  # ms

_DOMAIN_SCHEMA = vol.Optional(DOMAIN, default={CONF_I2CBUS: DEFAULT_I2CBUS})

CONFIG_SCHEMA = vol.Schema(
    {
        _DOMAIN_SCHEMA: vol.Schema(
            {
                vol.Optional(CONF_I2CBUS, default=DEFAULT_I2CBUS): vol.Coerce(int),
                vol.Optional(CONF_SCAN_PERIOD, default=DEFAULT_SCAN_PERIOD): vol.Coerce(
                    int
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up I2C bus from config and create the bus manager instance."""
    i2cbus = config[DOMAIN][CONF_I2CBUS]
    scan_interval = config[DOMAIN][CONF_SCAN_PERIOD]

    try:
        hass.data[DOMAIN] = I2cDeviceManager(i2cbus, scan_interval)
    except FileNotFoundError as exception:
        _LOGGER.warning(
            "Unable to open i2c bus: %s (%s)",
            exception.strerror,
            exception.filename,
        )
        return False

    # Callback function  when HA starts
    def start_polling(event):
        hass.data[DOMAIN].start_polling()

    # Callback function executed when HA stops
    def stop_polling(event):
        hass.data[DOMAIN].stop_polling()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_polling)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_polling)

    return True


class I2cDeviceManager(threading.Thread):
    """Threadsafe I2C bus manager taking care of i2c device registration, polling and access."""

    def __init__(self, i2cbus, scan_interval):
        """Initialize i2c bus manager."""
        threading.Thread.__init__(self)

        self._name = f"{type(self).__name__}"

        self._bus = smbus2.SMBus(i2cbus)
        self._scan_interval = float(scan_interval / 1000)

        self._run = False
        self._devices = []
        self._devices_lock = threading.Lock()

        _LOGGER.info(
            "%s created for i2c bus /dev/i2c-%d, scan period=%d ms",
            self._name,
            i2cbus,
            int(scan_interval),
        )

    def start_polling(self):
        """Start polling thread."""
        self._run = True
        self.start()

    def stop_polling(self):
        """Stop polling thread."""
        self._run = False
        self.join()

    def register_device(self, device_class, address, scan_multiple=None):
        """Create and append a device object to the manager device list or return an existing one if a device already exist at the same address."""
        with self._devices_lock:
            # Check for an existing instance at the same address and return it if it exists already
            for device in self._devices:
                if device["instance"].address == address:
                    if not isinstance(device["instance"], device_class):
                        _LOGGER.warning(
                            "Conflicting request for address 0x%02x: %s requested while %s exists already [UNCHANGED]",
                            address,
                            device_class.__name__,
                            type(device["instance"]).__name__,
                        )
                        return None

                    if scan_multiple:
                        if device["scan_multiple"]:
                            if scan_multiple != device["scan_multiple"]:
                                _LOGGER.warning(
                                    "Conflicting scan_multiple for %s@0x%02x: %d requested while it was %d [UNCHANGED]",
                                    type(device["instance"]).__name__,
                                    address,
                                    scan_multiple,
                                    device["scan_multiple"],
                                )
                        else:
                            device["scan_multiple"] = scan_multiple
                            device["scan_multiple_counter"] = scan_multiple
                            _LOGGER.info(
                                "Update %s@0x%02x (polling at %d x %d ms)",
                                device_class.__name__,
                                address,
                                scan_multiple,
                                int(1000 * self._scan_interval),
                            )

                    return device["instance"]

            # No device found -> create a new device_class instance
            self._devices.append(
                {
                    "instance": device_class(self, address),
                    "scan_multiple": scan_multiple,
                    "scan_multiple_counter": scan_multiple,
                }
            )
            if scan_multiple:
                _LOGGER.info(
                    "New %s@0x%02x registered (polling at %d x %d ms)",
                    device_class.__name__,
                    address,
                    scan_multiple,
                    int(1000 * self._scan_interval),
                )
            else:
                _LOGGER.info(
                    "New %s@0x%02x registered (no polling)",
                    device_class.__name__,
                    address,
                )

            return self._devices[-1]["instance"]

    def read_byte_data(self, address, register):
        """Read a single byte from designated register and i2c address."""
        return self._bus.read_byte_data(address, register)

    def write_byte_data(self, address, register, value):
        """Write a single byte to designated register and i2c address."""
        self._bus.write_byte_data(address, register, value)

    def run(self):
        """Thread main loop, scanning registered devices at configured period."""
        _LOGGER.info("%s starting", self._name)

        while self._run:
            # Protection against changes in the device list from other threads while running the loop
            # This is not required apriori because registering takes place before EVENT_HOMEASSISTANT_START/this thread is started
            with self._devices_lock:
                # Run all registered devices at their configured period if any
                for device in self._devices:
                    if device["scan_multiple_counter"]:
                        device["scan_multiple_counter"] -= 1
                        if device["scan_multiple_counter"] <= 0:
                            device["scan_multiple_counter"] = device["scan_multiple"]
                            device["instance"].run()

            time.sleep(self._scan_interval)

        _LOGGER.info("%s exiting", self._name)
