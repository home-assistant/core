"""The Synology SRM router class."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import synology_srm as srmlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DETECTION_TIME,
    CONF_NODE_ID,
    DEFAULT_DETECTION_TIME,
    DOMAIN,
    GET_NETWORK_NSM_DEVICE,
    GET_SYSTEM_INFO,
)
from .device import Device
from .errors import CannotConnect, LoginError

_LOGGER = logging.getLogger(__name__)

type SynologySRMConfigEntry = ConfigEntry[SynologySRMDataUpdateCoordinator]


class SynologySRMData:
    """Handle all communication with the Synology SRM API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: srmlib.Client,
    ) -> None:
        """Initialize the Synology SRM Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.api_client = api_client
        self._node_id: int = self.config_entry.data[CONF_NODE_ID]
        self._host: str = self.config_entry.data[CONF_HOST]
        self.all_devices: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, Device] = {}
        self.hostname: str = ""
        self.model: str = ""
        self.firmware: str = ""
        self.serial_number: str = ""

    @staticmethod
    def load_mac(devices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Load dictionary using MAC address as key."""
        mac_devices = {}
        for device in devices:
            if "mac" in device:
                mac = device["mac"]
                mac_devices[mac] = device
        return mac_devices

    def get_hub_details(self) -> None:
        """Get Hub info."""
        try:
            if data := self.command(GET_SYSTEM_INFO):
                # Get the node's information
                self.hostname = data[self._node_id]["unique"]
                self.model = data[self._node_id]["model"]
                self.firmware = data[self._node_id]["firmware_ver"]
                self.serial_number = data[self._node_id]["sn"]
            else:
                _LOGGER.error("Synology SRM %s node not found", self._node_id)

        except TimeoutError as err:
            _LOGGER.error("Synology SRM %s error: %s", self._host, err)
            raise CannotConnect from err

    def get_list_from_interface(self) -> dict[str, dict[str, Any]]:
        """Get devices from interface."""
        if result := self.command(GET_NETWORK_NSM_DEVICE):
            return self.load_mac(result)
        return {}

    def restore_device(self, mac: str) -> None:
        """Restore a missing device after restart."""
        self.devices[mac] = Device(mac, self.all_devices[mac])

    def update_devices(self) -> None:
        """Get list of devices with latest status."""
        try:
            self.all_devices = self.get_list_from_interface()
        except CannotConnect as err:
            raise UpdateFailed from err
        except LoginError as err:
            raise ConfigEntryAuthFailed from err

        if not self.all_devices:
            return

        for mac, params in self.all_devices.items():
            if mac not in self.devices:
                self.devices[mac] = Device(mac, self.all_devices.get(mac, {}))
            else:
                self.devices[mac].update(params=self.all_devices.get(mac, {}))

            if not params.get("is_online"):
                self.devices[mac].update(active=False)
                continue

            self.devices[mac].update(active=True)

    def command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        suppress_errors: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve data from Synology SRM Client API."""
        _LOGGER.debug("Running command %s", cmd)
        try:
            if cmd == GET_NETWORK_NSM_DEVICE:
                return list(self.api_client.core.get_network_nsm_device(params))
            if cmd == GET_SYSTEM_INFO:
                return list(self.api_client.mesh.get_system_info()["nodes"])

            raise ValueError(f"Unknown command: {cmd}")

        except (
            srmlib.http.SynologyHttpException,
            OSError,
            TimeoutError,
        ) as api_error:
            _LOGGER.error("Synology SRM %s connection error %s", self._host, api_error)
            # try to reconnect
            self.api_client = get_api_client(dict(self.config_entry.data))
            # we still have to raise CannotConnect to fail the update.
            raise CannotConnect from api_error
        except KeyError as api_error:
            emsg = "Synology SRM %s failed to retrieve data. cmd=[%s] Error: %s"
            if suppress_errors and "no such command prefix" in str(api_error):
                _LOGGER.debug(emsg, self._host, cmd, api_error)
                return []
            _LOGGER.warning(emsg, self._host, cmd, api_error)
            return []


class SynologySRMDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Synology SRM Hub Object."""

    config_entry: SynologySRMConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SynologySRMConfigEntry,
        api_client: srmlib.Client,
    ) -> None:
        """Initialize the Synology SRM Client."""
        self._srm_data = SynologySRMData(hass, config_entry, api_client)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=30),
        )

    @property
    def node_id(self) -> str:
        """Return the node id of this hub."""
        return str(self.config_entry.data[CONF_NODE_ID])

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return str(self.config_entry.data[CONF_HOST])

    @property
    def hostname(self) -> str:
        """Return the hostname of the hub."""
        return self._srm_data.hostname

    @property
    def model(self) -> str:
        """Return the model of the hub."""
        return self._srm_data.model

    @property
    def firmware(self) -> str:
        """Return the firmware of the hub."""
        return self._srm_data.firmware

    @property
    def serial_num(self) -> str:
        """Return the serial number of the hub."""
        return self._srm_data.serial_number

    @property
    def option_detection_time(self) -> timedelta:
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def api_client(self) -> SynologySRMData:
        """Represent Synology SRM data object."""
        return self._srm_data

    async def _async_update_data(self) -> None:
        """Update Synology SRM devices information."""
        await self.hass.async_add_executor_job(self._srm_data.update_devices)


def get_api_client(entry: dict[str, Any]) -> srmlib.Client:
    """Connect to Synology SRM hub."""
    _LOGGER.debug("Connecting to Synology SRM hub [%s]", entry[CONF_HOST])
    try:
        api_client = srmlib.Client(
            host=entry[CONF_HOST],
            port=entry[CONF_PORT],
            username=entry[CONF_USERNAME],
            password=entry[CONF_PASSWORD],
            https=entry[CONF_SSL],
        )

        if not entry[CONF_VERIFY_SSL]:
            api_client.http.disable_https_verify()

        # Trigger an API call to ensure the connection and trigger private function login is working
        api_client.http.call(
            endpoint="entry.cgi", api="SYNO.Mesh.System.Info", method="get", version=1
        )

    except srmlib.http.SynologyApiError as err:
        _LOGGER.error("Synology SRM %s error: %s", entry[CONF_HOST], err)
        if err.code in [401, 402, 403]:
            raise LoginError from err
        raise CannotConnect from err
    except (
        OSError,
        TimeoutError,
    ) as err:
        _LOGGER.error("Synology SRM %s error: %s", entry[CONF_HOST], err)
        raise CannotConnect from err

    _LOGGER.debug("Connected to %s successfully", entry[CONF_HOST])
    return api_client
