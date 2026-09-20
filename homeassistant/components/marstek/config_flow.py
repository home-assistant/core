"""Config flow for Marstek integration."""

import asyncio
import logging
from typing import override

from aiomarstek import MarstekDeviceInfo
from probatio import Required, Schema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_BLE_MAC,
    CONF_DEVICE_TYPE,
    CONF_VERSION,
    CONF_WIFI_MAC,
    CONF_WIFI_NAME,
    DOMAIN,
    SUPPORTED_DEVICE_TYPES,
)
from .coordinator import MARSTEK_SHARED_DATA
from .helpers import async_create_udp_client

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = Schema({Required(CONF_HOST): TextSelector()})


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek."""

    discovered_device_options: dict[str, MarstekDeviceInfo]

    def __init__(self) -> None:
        """Initialize the Marstek config flow."""
        self.discovery_task: asyncio.Task[None] | None = None
        self.discovered_devices: list[MarstekDeviceInfo] = []
        self.discovery_error: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_discover(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle broadcast device discovery."""
        if user_input and CONF_DEVICE in user_input:
            return await self._async_step_discover_selected_device(user_input)

        if self.discovery_task is None:
            self.discovery_task = self.hass.async_create_task(self._async_discover())

        if self.discovery_task.done():
            self.discovery_task.result()
            self.discovery_task = None
            return self.async_show_progress_done(next_step_id="discovery_done")

        return self.async_show_progress(
            step_id="discover",
            progress_action="discover",
            progress_task=self.discovery_task,
        )

    async def async_step_discovery_done(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Show the discovery results."""
        data_schema = (
            self._async_build_discovery_schema(self.discovered_devices)
            if self.discovered_devices
            else Schema({})
        )
        errors = {"base": self.discovery_error} if self.discovery_error else {}

        return self.async_show_form(
            step_id="discover", data_schema=data_schema, errors=errors
        )

    async def _async_step_discover_selected_device(
        self, user_input: dict[str, object]
    ) -> ConfigFlowResult:
        """Handle a selected discovered device."""
        errors: dict[str, str] = {}
        host = self.discovered_device_options[str(user_input[CONF_DEVICE])].ip

        try:
            device = await self._async_get_device_from_host(host)
        except TimeoutError, OSError:
            errors["base"] = "cannot_connect"
        except TypeError:
            errors["base"] = "device_not_found"
        else:
            return await self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="discover",
            data_schema=Schema({}),
            errors=errors,
        )

    async def _async_discover(self) -> None:
        """Discover supported Marstek devices."""
        self.discovered_devices = []
        self.discovery_error = None
        _LOGGER.debug("Starting device discovery")
        shared_data = self.hass.data.get(MARSTEK_SHARED_DATA)
        udp_client = shared_data.udp_client if shared_data is not None else None
        try:
            if udp_client is None:
                udp_client = await async_create_udp_client(self.hass)
            try:
                discovered_devices = await udp_client.discover_devices()
            finally:
                if shared_data is None:
                    await udp_client.async_cleanup()
        except TimeoutError, OSError, TypeError:
            self.discovery_error = "discovery_failed"
            return

        if not discovered_devices:
            self.discovery_error = "no_devices_found"
            return

        self.discovered_devices = [
            device
            for device in discovered_devices
            if device.device_type in SUPPORTED_DEVICE_TYPES
        ]
        if not self.discovered_devices:
            self.discovery_error = "unsupported_device"
            return

        _LOGGER.debug(
            "Discovered %d supported devices out of %d total",
            len(self.discovered_devices),
            len(discovered_devices),
        )

    def _async_build_discovery_schema(
        self, supported_devices: list[MarstekDeviceInfo]
    ) -> Schema:
        """Build the discovery form schema from supported devices."""
        self.discovered_device_options = {}

        device_options: list[SelectOptionDict] = []
        for index, device in enumerate(supported_devices):
            device_label = (
                f"{device.device_type} v{device.version} "
                f"({device.wifi_name or 'No WiFi'}) - {device.ip or 'Unknown IP'}"
            )
            if any(option["label"] == device_label for option in device_options):
                device_label = f"{device_label} #{index + 1}"

            device_key = str(index)
            self.discovered_device_options[device_key] = device
            device_options.append(
                SelectOptionDict(value=device_key, label=device_label)
            )

        return Schema(
            {
                Required(CONF_DEVICE): SelectSelector(
                    SelectSelectorConfig(options=device_options)
                )
            }
        )

    async def async_step_manual(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST])
            self._async_abort_entries_match({CONF_HOST: host})

            try:
                device = await self._async_get_device_from_host(host)
            except TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except TypeError:
                errors["base"] = "device_not_found"
            else:
                if device.device_type not in SUPPORTED_DEVICE_TYPES:
                    errors["base"] = "unsupported_device"
                else:
                    return await self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_get_device_from_host(self, host: str) -> MarstekDeviceInfo:
        """Fetch device information from a specific host."""
        shared_data = self.hass.data.get(MARSTEK_SHARED_DATA)
        udp_client = shared_data.udp_client if shared_data is not None else None
        try:
            if udp_client is None:
                udp_client = await async_create_udp_client(self.hass)
            return await udp_client.get_device_info(host)
        finally:
            if shared_data is None and udp_client is not None:
                await udp_client.async_cleanup()

    async def _async_create_entry_from_device(
        self, device: MarstekDeviceInfo
    ) -> ConfigFlowResult:
        """Create a config entry from normalized Marstek device data."""
        if device.device_type not in SUPPORTED_DEVICE_TYPES:
            return self.async_abort(reason="unsupported_device")

        unique_id = device.stable_id
        if not unique_id:
            return self.async_abort(reason="missing_unique_id")

        _LOGGER.debug(
            "Check device uniqueness: IP=%s, MAC=%s, unique_id=%s",
            device.ip,
            device.mac,
            unique_id,
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.ip})

        return self.async_create_entry(
            title=f"Marstek {device.device_type} v{device.version} ({device.ip})",
            data={
                CONF_HOST: device.ip,
                CONF_MAC: device.mac,
                CONF_DEVICE_TYPE: device.device_type,
                CONF_VERSION: device.version,
                CONF_WIFI_NAME: device.wifi_name,
                CONF_WIFI_MAC: device.wifi_mac,
                CONF_BLE_MAC: device.ble_mac,
            },
        )
