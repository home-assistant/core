"""Config flow for Marstek integration."""

import logging
from typing import override

from aiomarstek import MarstekUDPClient
from probatio import Required as VolRequired, Schema as VolSchema

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import DOMAIN
from .helpers import async_create_udp_client
from .models import MarstekDeviceInfo

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = VolSchema({VolRequired(CONF_HOST): TextSelector()})


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
            return await self._async_step_discover_selected_device(user_input)

        data_schema, errors = await self._async_get_discovery_form()

        return self.async_show_form(
            step_id="discover",
            data_schema=data_schema,
            errors=errors,
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
                if not device.is_supported:
                    errors["base"] = "unsupported_device"
                    return self.async_show_form(
                        step_id="manual",
                        data_schema=STEP_MANUAL_DATA_SCHEMA,
                        errors=errors,
                    )
                return await self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
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
            data_schema=VolSchema({}),
            errors=errors,
        )

    async def _async_get_discovery_form(
        self,
    ) -> tuple[VolSchema, dict[str, str]]:
        """Discover devices and build the selection form."""
        errors: dict[str, str] = {}
        data_schema = VolSchema({})

        _LOGGER.debug("Starting device discovery")
        supported_devices = await self._async_get_supported_discovered_devices(errors)
        if supported_devices is None:
            return data_schema, errors

        data_schema = self._async_build_discovery_schema(supported_devices)
        return data_schema, errors

    async def _async_get_supported_discovered_devices(
        self, errors: dict[str, str]
    ) -> list[MarstekDeviceInfo] | None:
        """Return supported discovered devices or record an error."""
        udp_client: MarstekUDPClient | None = None
        try:
            try:
                udp_client = await async_create_udp_client(self.hass)
                discovered_devices = await udp_client.discover_devices()
            finally:
                if udp_client is not None:
                    await udp_client.async_cleanup()
        except TimeoutError, OSError, TypeError:
            errors["base"] = "discovery_failed"
            return None

        if not discovered_devices:
            errors["base"] = "no_devices_found"
            return None

        normalized_devices = [
            MarstekDeviceInfo.from_response(device) for device in discovered_devices
        ]
        supported_devices = [
            device for device in normalized_devices if device.is_supported
        ]
        if not supported_devices:
            errors["base"] = "unsupported_device"
            return None

        _LOGGER.debug(
            "Discovered %d supported devices out of %d total",
            len(supported_devices),
            len(normalized_devices),
        )
        return supported_devices

    def _async_build_discovery_schema(
        self, supported_devices: list[MarstekDeviceInfo]
    ) -> VolSchema:
        """Build the discovery form schema from supported devices."""
        self.discovered_device_options = {}

        device_options: list[SelectOptionDict] = []
        for index, device in enumerate(supported_devices):
            device_label = device.display_name
            if any(option["label"] == device_label for option in device_options):
                device_label = f"{device_label} #{index + 1}"

            device_key = str(index)
            self.discovered_device_options[device_key] = device
            device_options.append(
                SelectOptionDict(value=device_key, label=device_label)
            )

        return VolSchema(
            {
                VolRequired(CONF_DEVICE): SelectSelector(
                    SelectSelectorConfig(options=device_options)
                )
            }
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
        if not device.is_supported:
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
            title=device.title,
            data=device.as_config_entry_data(),
        )
