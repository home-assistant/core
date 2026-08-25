"""Config flow for Marstek integration."""

import logging
from typing import override

from aiomarstek import MarstekUDPClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from . import async_create_udp_client
from .const import DOMAIN
from .models import MarstekDeviceInfo

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): TextSelector()})
ABORT_MISSING_UNIQUE_ID = "missing_unique_id"
MARSTEK_CONNECTION_ERRORS = (TimeoutError, OSError)
MARSTEK_DISCOVERY_ERRORS = (TimeoutError, OSError, TypeError)
MARSTEK_DEVICE_INFO_ERRORS = (TypeError,)


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek."""

    discovered_device_options: dict[str, MarstekDeviceInfo]

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
            host = self.discovered_device_options[str(user_input[CONF_DEVICE])].ip
            try:
                device = await self._async_get_device_from_host(host)
            except MARSTEK_CONNECTION_ERRORS:
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema({}),
                    errors={"base": "cannot_connect"},
                )
            except MARSTEK_DEVICE_INFO_ERRORS:
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema({}),
                    errors={"base": "device_not_found"},
                )
            return await self._async_create_entry_from_device(device)

        _LOGGER.debug("Starting device discovery")
        try:
            udp_client: MarstekUDPClient | None = None
            try:
                udp_client = await async_create_udp_client(self.hass)
                discovered_devices = await udp_client.discover_devices()
            finally:
                if udp_client is not None:
                    await udp_client.async_cleanup()
        except MARSTEK_DISCOVERY_ERRORS:
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors={"base": "discovery_failed"},
            )

        if not discovered_devices:
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices_found"},
            )

        normalized_devices = [
            MarstekDeviceInfo.from_response(device) for device in discovered_devices
        ]
        _LOGGER.debug("Discovered %d devices", len(normalized_devices))
        self.discovered_device_options = {}

        device_options: list[SelectOptionDict] = []
        for index, device in enumerate(normalized_devices):
            device_label = device.display_name
            if any(option["label"] == device_label for option in device_options):
                device_label = f"{device_label} #{index + 1}"
            device_key = str(index)
            self.discovered_device_options[device_key] = device
            device_options.append(
                SelectOptionDict(value=device_key, label=device_label)
            )

        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(options=device_options)
                    )
                }
            ),
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
            except MARSTEK_CONNECTION_ERRORS:
                errors["base"] = "cannot_connect"
            except MARSTEK_DEVICE_INFO_ERRORS:
                errors["base"] = "device_not_found"
            else:
                return await self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_get_device_from_host(self, host: str) -> MarstekDeviceInfo:
        """Fetch device information from a specific host."""
        udp_client: MarstekUDPClient | None = None
        try:
            udp_client = await async_create_udp_client(self.hass)
            device_info = await udp_client.get_device_info(host)
            if not isinstance(device_info, dict):
                raise TypeError("No device information returned")
            return MarstekDeviceInfo.from_response(device_info, host)
        finally:
            if udp_client is not None:
                await udp_client.async_cleanup()

    async def _async_create_entry_from_device(
        self, device: MarstekDeviceInfo
    ) -> ConfigFlowResult:
        """Create a config entry from normalized Marstek device data."""
        unique_id = device.stable_id
        if not unique_id:
            return self.async_abort(reason=ABORT_MISSING_UNIQUE_ID)

        _LOGGER.debug(
            "Check device uniqueness: IP=%s, MAC=%s, unique_id=%s",
            device.ip,
            device.mac,
            unique_id,
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.ip})

        return self.async_create_entry(
            title=device.title,
            data=device.as_config_entry_data(),
        )
