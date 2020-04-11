"""The nut component."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from pynut2.nut2 import PyNUTClient, PyNUTError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR,
    DOMAIN,
    PLATFORMS,
    PYNUT_DATA,
    PYNUT_FIRMWARE,
    PYNUT_MANUFACTURER,
    PYNUT_MODEL,
    PYNUT_NAME,
    PYNUT_UNIQUE_ID,
    UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Network UPS Tools (NUT) component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Network UPS Tools (NUT) from a config entry."""

    config = entry.data
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    alias = config.get(CONF_ALIAS)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    data = PyNUTData(host, port, alias, username, password)

    async def async_update_data():
        """Fetch data from NUT."""
        async with async_timeout.timeout(10):
            return await hass.async_add_executor_job(data.update)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NUT resource status",
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()
    status = data.status

    if not status:
        _LOGGER.error("NUT Sensor has no data, unable to set up")
        raise ConfigEntryNotReady

    _LOGGER.debug("NUT Sensors Available: %s", status)

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        PYNUT_DATA: data,
        PYNUT_UNIQUE_ID: _unique_id_from_status(status),
        PYNUT_MANUFACTURER: _manufacturer_from_status(status),
        PYNUT_MODEL: _model_from_status(status),
        PYNUT_FIRMWARE: _firmware_from_status(status),
        PYNUT_NAME: data.name,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _manufacturer_from_status(status):
    """Find the best manufacturer value from the status."""
    return (
        status.get("device.mfr")
        or status.get("ups.mfr")
        or status.get("ups.vendorid")
        or status.get("driver.version.data")
    )


def _model_from_status(status):
    """Find the best model value from the status."""
    return (
        status.get("device.model")
        or status.get("ups.model")
        or status.get("ups.productid")
    )


def _firmware_from_status(status):
    """Find the best firmware value from the status."""
    return status.get("ups.firmware") or status.get("ups.firmware.aux")


def _serial_from_status(status):
    """Find the best serialvalue from the status."""
    serial = status.get("device.serial") or status.get("ups.serial")
    if serial and serial == "unknown":
        return None
    return serial


def _unique_id_from_status(status):
    """Find the best unique id value from the status."""
    serial = _serial_from_status(status)
    # We must have a serial for this to be unique
    if not serial:
        return None

    manufacturer = _manufacturer_from_status(status)
    model = _model_from_status(status)

    unique_id_group = []
    if manufacturer:
        unique_id_group.append(manufacturer)
    if model:
        unique_id_group.append(model)
    if serial:
        unique_id_group.append(serial)
    return "_".join(unique_id_group)


def find_resources_in_config_entry(config_entry):
    """Find the configured resources in the config entry."""
    if CONF_RESOURCES in config_entry.options:
        return config_entry.options[CONF_RESOURCES]
    return config_entry.data[CONF_RESOURCES]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PyNUTData:
    """Stores the data retrieved from NUT.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port, alias, username, password):
        """Initialize the data object."""

        self._host = host
        self._alias = alias

        # Establish client with persistent=False to open/close connection on
        # each update call.  This is more reliable with async.
        self._client = PyNUTClient(self._host, port, username, password, 5, False)
        self.ups_list = None
        self._status = None

    @property
    def status(self):
        """Get latest update if throttle allows. Return status."""
        return self._status

    @property
    def name(self):
        """Return the name of the ups."""
        return self._alias

    def _get_alias(self):
        """Get the ups alias from NUT."""
        try:
            ups_list = self._client.list_ups()
        except PyNUTError as err:
            _LOGGER.error("Failure getting NUT ups alias, %s", err)
            return None

        if not ups_list:
            _LOGGER.error("Empty list while getting NUT ups aliases")
            return None

        self.ups_list = ups_list
        return list(ups_list)[0]

    def _get_status(self):
        """Get the ups status from NUT."""
        if self._alias is None:
            self._alias = self._get_alias()

        try:
            return self._client.list_vars(self._alias)
        except (PyNUTError, ConnectionResetError) as err:
            _LOGGER.debug("Error getting NUT vars for host %s: %s", self._host, err)
            return None

    def update(self, **kwargs):
        """Fetch the latest status from NUT."""
        self._status = self._get_status()
