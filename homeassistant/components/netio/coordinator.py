"""Data update coordinator for the Netio integration."""

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, override

from Netio import Netio
from Netio.exceptions import AuthError, CommunicationError
import requests

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
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 10

type NetioConfigEntry = ConfigEntry[NetioDataUpdateCoordinator]


def device_base_url(data: Mapping[str, Any]) -> str:
    """Return the base URL of the device web interface."""
    scheme = "https" if data[CONF_SSL] else "http"
    return f"{scheme}://{data[CONF_HOST]}:{data[CONF_PORT]}"


def create_device(data: Mapping[str, Any]) -> Netio:
    """Create a Netio JSON API client, connecting to the device."""
    return Netio(
        f"{device_base_url(data)}/netio.json",
        auth_rw=(data[CONF_USERNAME], data[CONF_PASSWORD]),
        verify=data[CONF_VERIFY_SSL],
        timeout=REQUEST_TIMEOUT,
    )


class NetioDataUpdateCoordinator(DataUpdateCoordinator[dict[int, Netio.OUTPUT]]):
    """Coordinator fetching output states from a Netio device."""

    config_entry: NetioConfigEntry
    device: Netio
    device_info: DeviceInfo

    def __init__(self, hass: HomeAssistant, config_entry: NetioConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {config_entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    def _connect_device(self) -> tuple[Netio, dict[str, Any]]:
        """Connect to the device and fetch device information."""
        device = create_device(self.config_entry.data)
        return device, device.get_info()

    @override
    async def _async_setup(self) -> None:
        """Connect to the device and prepare device info."""
        try:
            self.device, info = await self.hass.async_add_executor_job(
                self._connect_device
            )
        except AuthError as err:
            raise ConfigEntryError("Invalid authentication") from err
        except (CommunicationError, requests.RequestException) as err:
            raise UpdateFailed(f"Cannot connect to device: {err}") from err

        agent = info.get("Agent", {})
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.SerialNumber)},
            name=self.device.DeviceName,
            manufacturer="NETIO products",
            model=agent.get("Model"),
            sw_version=agent.get("Version"),
            configuration_url=device_base_url(self.config_entry.data),
        )
        if mac := agent.get("MAC"):
            self.device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }

    @override
    async def _async_update_data(self) -> dict[int, Netio.OUTPUT]:
        """Fetch output states from the device."""
        try:
            outputs = await self.hass.async_add_executor_job(self.device.get_outputs)
        except (AuthError, CommunicationError, requests.RequestException) as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        return {output.ID: output for output in outputs}

    async def async_set_output(self, output_id: int, state: bool) -> None:
        """Set the state of an output and refresh."""
        action = Netio.ACTION.ON if state else Netio.ACTION.OFF
        try:
            await self.hass.async_add_executor_job(
                self.device.set_output, output_id, action
            )
        except (AuthError, CommunicationError, requests.RequestException) as err:
            raise HomeAssistantError(
                f"Error setting output {output_id}: {err}"
            ) from err
        await self.async_request_refresh()
