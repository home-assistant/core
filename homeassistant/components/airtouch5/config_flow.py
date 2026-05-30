"""Config flow for Airtouch 5 integration."""

import logging
from typing import Any

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.discovery import AirtouchDevice, AirtouchDiscovery
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AirTouch5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airtouch 5."""

    VERSION = 2
    devices: list[AirtouchDevice] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        devices = await self._discovery()
        options = {
            f"{device.system_id:}": f"{device.name} - {device.ip}" for device in devices
        }
        options["manual"] = "Manual Entry"  # Placeholder option
        self.devices = devices

        schema = vol.Schema({vol.Required("Select Device"): vol.In(options)})
        return self.async_show_form(step_id="choose", data_schema=schema)

    async def async_step_choose(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            client = Airtouch5SimpleClient(user_input[CONF_HOST])
            try:
                await client.test_connection()
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "cannot_connect"}
            else:
                # Uses the host/IP value from CONF_HOST as unique ID,
                # which is no longer allowed
                # pylint: disable-next=home-assistant-unique-id-ip-based
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="manual", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual entry step."""
        errors: dict[str, str] | None = None
        host = user_input.get(CONF_HOST) if user_input else None
        if not host:
            # No input yet, show the manual entry form
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        host_str = str(host)
        device = None  # initialise device variable to None so that it is in scope after the Try block, whether or not the discovery by IP is successful.
        try:
            device = await self._discover_device_by_ip(host_str)
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors = {"base": "device_not_found"}

        if device:
            await self.async_set_unique_id(device.system_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{device.name} ({device.system_id})",
                data={
                    "system_id": device.system_id,
                    "host": device.ip,
                    "model": device.model,
                    "console_id": device.console_id,
                    "name": device.name,
                },
            )

        client = Airtouch5SimpleClient(host_str)
        try:
            await client.test_connection()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors = {"base": "cannot_connect"}
            return self.async_show_form(
                step_id="manual",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )
        await self.async_set_unique_id(host_str)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=host_str, data={CONF_HOST: host_str})

    async def _discovery(self) -> list[AirtouchDevice]:
        """Discover Airtouch devices on the network."""
        devices: list[AirtouchDevice] = []
        AirtouchDiscovery_instance = AirtouchDiscovery()
        try:
            await AirtouchDiscovery_instance.establish_server()
            devices = await AirtouchDiscovery_instance.discover()
            _LOGGER.info("Finished waiting for airtouch device")
        except Exception:
            _LOGGER.exception("Unexpected exception during discovery")
        finally:
            await AirtouchDiscovery_instance.close()
        return devices

    async def _discover_device_by_ip(self, host: str) -> AirtouchDevice | None:
        """Discover a single Airtouch device by IP."""
        host_str = str(host)
        AirtouchDiscovery_instance = AirtouchDiscovery()
        try:
            await AirtouchDiscovery_instance.establish_server()
            device = await AirtouchDiscovery_instance.discover_by_ip(host_str)
            _LOGGER.info("Finished waiting for airtouch device")
            return device
        finally:
            await AirtouchDiscovery_instance.close()
