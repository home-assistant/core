"""Representation of an OWServer proxy."""
from glob import glob
import os
import time

from pyownet import protocol

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import callback

from .const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    CONF_TYPE_OWFS,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_SYSBUS_MOUNT_DIR,
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
        self.conf_type = None
        self._owproxy = None
        self._base_dir = None
        self._device_names = {}
        if CONF_NAMES in config:
            if isinstance(config[CONF_NAMES], dict):
                self._device_names = config[CONF_NAMES]

    def get_device_name(self, device_id):
        """Return device name if specified in the config."""
        return self._device_names.get(device_id, device_id)

    def setup(self):
        """Check connectivity."""
        LOGGER.debug("Initializing using %s", self.config)
        self.conf_type = self.config.get(CONF_TYPE)
        conf_host = self.config.get(CONF_HOST)
        conf_port = self.config.get(CONF_PORT)
        conf_mount_dir = self.config.get(CONF_MOUNT_DIR)

        # Ensure type is configured
        if self.conf_type is None:
            if conf_host:
                self.conf_type = CONF_TYPE_OWSERVER
            elif conf_mount_dir == DEFAULT_SYSBUS_MOUNT_DIR:
                self.conf_type = CONF_TYPE_SYSBUS
            else:
                self.conf_type = CONF_TYPE_OWFS

        if self.conf_type == CONF_TYPE_OWSERVER:
            LOGGER.debug("Initializing using %s:%s", conf_host, conf_port)
            try:
                self._owproxy = protocol.proxy(host=conf_host, port=conf_port)
                self._owproxy.dir()
                return True
            except protocol.Error as exc:
                LOGGER.error(
                    "Cannot connect to owserver on %s:%d, got: %s",
                    conf_host,
                    conf_port,
                    exc,
                )
                return False
        else:
            self._base_dir = conf_mount_dir
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
        if self.conf_type == CONF_TYPE_OWSERVER:
            for device_path in self._owproxy.dir():
                device_id = device_path.replace("/", "")
                devices[device_id] = device_path
        elif self.conf_type == CONF_TYPE_SYSBUS:
            device_family = "28"
            for device_folder in glob(
                os.path.join(self._base_dir, f"{device_family}[.-]*")
            ):
                device_id = os.path.split(device_folder)[1]
                device_path = os.path.join(device_folder, "")
                devices[device_id] = device_path
        elif self.conf_type == CONF_TYPE_OWFS:
            for family_file_path in glob(os.path.join(self._base_dir, "*", "family")):
                device_id = os.path.split(os.path.split(family_file_path)[0])[1]
                device_path = os.path.join(os.path.split(family_file_path)[0], "")
                devices[device_id] = device_path
        return devices

    def is_present(self, device_path):
        """Check that the device is present."""
        if self.conf_type == CONF_TYPE_OWSERVER:
            return self._owproxy.present(device_path)

        return os.path.exists(device_path)

    def read_family(self, device):
        """Read the device family."""
        if self.conf_type == CONF_TYPE_SYSBUS:
            parent = os.path.split(device)[0]
            return os.path.split(parent)[1][:2]

        return self.read_value(f"{device}family")

    def read_type(self, device):
        """Read the device type."""
        if self.conf_type == CONF_TYPE_SYSBUS:
            parent = os.path.split(device)[0]
            return os.path.split(parent)[1][:2]

        return self.read_value(f"{device}type")

    def read_value(self, device_path):
        """Read the device value."""
        if self.conf_type == CONF_TYPE_OWSERVER:
            return self._owproxy.read(device_path).decode().lstrip()
        if self.conf_type == CONF_TYPE_SYSBUS:
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
