"""Representation of an OWServer proxy."""
from glob import glob
import os
import time

from pyownet import protocol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    DEFAULT_MOUNT_DIR,
    DOMAIN,
    LOGGER,
    SUPPORTED_PLATFORMS,
)


@callback
def get_proxy_from_config_entry(hass, config_entry):
    """Return proxy with a matching unique id."""
    return hass.data[DOMAIN].get(config_entry.entry_id)


class OneWireProxy:
    """Manages a proxy for owserver/owfs/sysbus."""

    def __init__(self, hass, config) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config = config
        self._owproxy = None
        self._base_dir = None
        self._device_names = {}
        if CONF_NAMES in config:
            if isinstance(config[CONF_NAMES], dict):
                self._device_names = config[CONF_NAMES]

    def get_device_name(self, device_id):
        """Return device name if specified in the config."""
        return self._device_names.get(device_id, device_id)

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
        devices = {}
        if self._owproxy:
            for device_path in self._owproxy.dir():
                device_id = device_path.replace("/", "")
                devices[device_id] = device_path
        elif self.is_sysbus:
            device_family = "28"
            for device_folder in glob(
                os.path.join(self._base_dir, f"{device_family}[.-]*")
            ):
                device_id = os.path.split(device_folder)[1]
                device_path = os.path.join(device_folder, "")
                devices[device_id] = device_path
        else:
            for family_file_path in glob(os.path.join(self._base_dir, "*", "family")):
                device_id = os.path.split(os.path.split(family_file_path)[0])[1]
                device_path = os.path.join(os.path.split(family_file_path)[0], "")
                devices[device_id] = device_path
        return devices

    def is_present(self, device_path):
        """Check that the device is present."""
        if self._owproxy:
            return self._owproxy.present(device_path)

        return os.path.exists(device_path)

    def read_family(self, device):
        """Read the device family."""
        if self.is_sysbus:
            parent = os.path.split(device)[0]
            return os.path.split(parent)[1][:2]

        return self.read_value(f"{device}family")

    def read_type(self, device):
        """Read the device type."""
        if self.is_sysbus:
            parent = os.path.split(device)[0]
            return os.path.split(parent)[1][:2]

        return self.read_value(f"{device}type")

    def read_value(self, device_path):
        """Read the device value."""
        if self._owproxy:
            return self._owproxy.read(device_path).decode().lstrip()
        if self.is_sysbus:
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

        with open(device_path) as ds_device_file:
            lines = ds_device_file.readlines()
        if len(lines) == 1:
            return lines[0]
        return lines

    def write_value(self, device_path, value):
        """Write the device value."""
        if self._owproxy:
            self._owproxy.write(device_path, value)
        else:
            with open(device_path) as ds_device_file:
                ds_device_file.write(value)
