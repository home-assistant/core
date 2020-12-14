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
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_I2CBUS = 1
DEFAULT_SCAN_INTERVAL = 100  # ms

_DOMAIN_SCHEMA = vol.Optional(DOMAIN, default={CONF_I2CBUS: DEFAULT_I2CBUS})

CONFIG_SCHEMA = vol.Schema(
    {
        _DOMAIN_SCHEMA: vol.Schema(
            {
                vol.Optional(CONF_I2CBUS, default=DEFAULT_I2CBUS): vol.Coerce(int),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.Coerce(int),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up I2C bus from config and create the bus manager instance."""
    i2cbus = config[DOMAIN][CONF_I2CBUS]
    scan_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    try:
        hass.data[DOMAIN] = I2cDeviceManager(i2cbus, scan_interval)
    except FileNotFoundError as exception:
        _LOGGER.error(
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

    # Start polling if hass is running already otherwise schedule it
    if hass.is_running:
        hass.data[DOMAIN].start_polling()
    else:
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
        self._scan_interval = float(scan_interval) / 1000.0

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

    def register_device(self, device):
        """Add device reference to the manager device list for supplied address."""
        with self._devices_lock:
            for existing_device in self._devices:
                # Raise an exception if an instance exists already at the same address
                if device.address == existing_device.address:
                    _LOGGER.warning(
                        "Conflicting request for address 0x%02x: %s requested while %s exists already [UNCHANGED]",
                        device.address,
                        type(device).__name__,
                        type(existing_device).__name__,
                    )
                    raise ValueError

            self._devices.append(device)

        _LOGGER.info("New %s@0x%02x registered", type(device).__name__, device.address)

    def unregister_device(self, device):
        """Remove device reference from the manager device list."""
        with self._devices_lock:
            if device in self._devices:
                self._devices.remove(device)
        _LOGGER.info("%s@0x%02x removed", type(device).__name__, device.address)

    def read_byte_data(self, address, register):
        """Read a single byte from designated register and i2c address."""
        return self._bus.read_byte_data(address, register)

    def write_byte_data(self, address, register, value):
        """Write a single byte to designated register and i2c address."""
        self._bus.write_byte_data(address, register, value)

    def read_word_data(self, address, register):
        """Read a single word from designated register and i2c address."""
        return self._bus.read_word_data(address, register)

    def write_word_data(self, address, register, value):
        """Write a single word to designated register and i2c address."""
        self._bus.write_word_data(address, register, value)

    def run(self):
        """Thread main loop, scanning registered devices at configured period."""
        _LOGGER.info("%s starting", self._name)

        while self._run:
            # Protection against changes in the device list from other threads while running the loop
            # This is not required apriori because registering takes place before EVENT_HOMEASSISTANT_START/this thread is started
            with self._devices_lock:
                # Run all registered devices
                for device in self._devices:
                    if hasattr(device, "run"):
                        device.run()

            time.sleep(self._scan_interval)

        _LOGGER.info("%s exiting", self._name)
