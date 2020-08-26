"""Representation of an OWServer proxy."""
import os
import time
from glob import glob

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_MOUNT_DIR,
    DEFAULT_MOUNT_DIR,
    DOMAIN,
    LOGGER,
    SUPPORTED_PLATFORMS,
)


from pyownet import protocol


@callback
def get_proxy_from_config_entry(hass, config_entry):
    """Return proxy with a matching unique id."""
    return hass.data[DOMAIN].get(config_entry.entry_id)


class OneWireProxy:
    """Manages a single owserver proxy."""

    def __init__(self, hass, config) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config = config
        self._owproxy = None
        self._base_dir = None

    @property
    def is_sysbus(self):
        """Return True if using raw GPIO ow sensor on a Pi."""
        return self._base_dir == DEFAULT_MOUNT_DIR

    def setup(self):
        """Check connectivity."""
        self._base_dir = self.config.get(CONF_MOUNT_DIR)
        owhost = self.config.get(CONF_HOST)
        owport = self.config.get(CONF_PORT)
        if owhost:
            LOGGER.debug("Initializing using %s:%s", owhost, owport)
            try:
                self._owproxy = protocol.proxy(host=owhost, port=owport)
                self._owproxy.dir()
                return True
            except protocol.Error as exc:
                LOGGER.error(
                    "Cannot connect to owserver on %s:%d, got: %s", owhost, owport, exc
                )
                return False
        else:
            LOGGER.debug("Initializing using %s", self._base_dir)
            if not os.path.isdir(self._base_dir):
                LOGGER.error(
                    "Cannot connect to one-wire instance: %s is not a directory.",
                    self._base_dir,
                )
                return False
        return True

    def load_entities(self, config_entry):
        """Load all entities."""
        for component in SUPPORTED_PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    config_entry, component
                )
            )

    def read_device_list(self):
        """Read the devices from the path."""
        if self._owproxy:
            return self._owproxy.dir()
        elif self.is_sysbus:
            devices = []
            device_family = "28"
            for device_folder in glob(
                os.path.join(self._base_dir, f"{device_family}[.-]*")
            ):
                devices.append(os.path.join(device_folder, ""))
            return devices
        else:
            devices = []
            for family_file_path in glob(os.path.join(self._base_dir, "*", "family")):
                devices.append(os.path.join(os.path.split(family_file_path)[0], ""))
            return devices

    def is_present(self, device_path):
        """Check that the path exists."""
        if self._owproxy:
            return self._owproxy.present(device_path)
        else:
            return os.path.exists(device_path)

    def read_family(self, device):
        """Read the device family."""
        if self.is_sysbus:
            parent = os.path.split(device)[0]
            return os.path.split(parent)[1][:2]
        else:
            return self.read_value(f"{device}family")

    def read_value(self, device_path):
        """Read the value from the path."""
        if self._owproxy:
            return self._owproxy.read(device_path).decode().lstrip()
        elif self.is_sysbus:
            w1_slave_path = os.path.split(device_path)[0]
            w1_slave_path = os.path.join(w1_slave_path, "w1_slave")
            with open(w1_slave_path) as ds_device_file:
                lines = ds_device_file.readlines()
            while lines[0].strip()[-3:] != "YES":
                time.sleep(0.2)
                with open(w1_slave_path) as ds_device_file:
                    lines = ds_device_file.readlines()
            equals_pos = lines[1].find("t=")
            if equals_pos != -1:
                value_string = lines[1][equals_pos + 2 :]
                return value_string
        else:
            with open(device_path) as ds_device_file:
                lines = ds_device_file.readlines()
            if len(lines) == 1:
                return lines[0]
            return lines

    def write_value(self, device_path, value):
        """Write the value to the path."""
        if self._owproxy:
            self._owproxy.write(device_path, value)
        else:
            with open(device_path) as ds_device_file:
                ds_device_file.write(value)
