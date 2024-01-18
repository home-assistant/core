"""Config flow for linknlink devices."""
import errno
from functools import partial
import logging
import socket
from typing import Any

import linknlink as llk
from linknlink.exceptions import (
    AuthenticationError,
    LinknLinkException,
    NetworkTimeoutError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_TYPE
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_TIMEOUT, DEVICE_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class linknlinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a linknlink config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the linknlink flow."""
        self.device: llk.Device = None

    async def async_set_device(self, device: llk.Device, raise_on_progress=True):
        """Define a device for the config flow."""
        if device.type not in DEVICE_TYPES:
            _LOGGER.error(
                ("Unsupported device: %s"),
                hex(device.devtype),
            )
            raise AbortFlow("not_supported")

        await self.async_set_unique_id(
            device.mac.hex(), raise_on_progress=raise_on_progress
        )
        self.device = device

        self.context["title_placeholders"] = {
            "name": device.name,
            "model": device.model,
            "host": device.host[0],
        }

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        host = discovery_info.ip
        unique_id = discovery_info.macaddress.lower().replace(":", "")
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            device = await self.hass.async_add_executor_job(llk.hello, host)

        except NetworkTimeoutError:
            return self.async_abort(reason="cannot_connect")

        except OSError as err:
            if err.errno == errno.ENETUNREACH:
                return self.async_abort(reason="cannot_connect")
            return self.async_abort(reason="unknown")

        if device.type not in DEVICE_TYPES:
            return self.async_abort(reason="not_supported")

        await self.async_set_device(device)
        return await self.async_step_auth()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input:
            host = user_input[CONF_HOST]
            timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

            try:
                hello = partial(llk.hello, host, timeout=timeout)
                linknlink = await self.hass.async_add_executor_job(hello)

            except NetworkTimeoutError:
                errors["base"] = "cannot_connect"
                err_msg = "Device not found"

            except OSError as err:
                if err.errno in {errno.EINVAL, socket.EAI_NONAME}:
                    errors["base"] = "invalid_host"
                    err_msg = "Invalid hostname or IP address"
                elif err.errno == errno.ENETUNREACH:
                    errors["base"] = "cannot_connect"
                    err_msg = str(err)
                else:
                    errors["base"] = "unknown"
                    err_msg = str(err)

            else:
                linknlink.timeout = timeout

                await self.async_set_device(linknlink)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: linknlink.host[0], CONF_TIMEOUT: timeout}
                )
                return await self.async_step_auth()

            _LOGGER.error("Failed to connect to the device at %s: %s", host, err_msg)

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_auth(self) -> FlowResult:
        """Authenticate to the device."""
        device = self.device
        errors = {}

        try:
            await self.hass.async_add_executor_job(device.auth)

        except AuthenticationError:
            errors["base"] = "invalid_auth"
            await self.async_set_unique_id(device.mac.hex())
            return await self.async_step_reset(errors=errors)

        except NetworkTimeoutError as err:
            errors["base"] = "cannot_connect"
            err_msg = str(err)

        except LinknLinkException as err:
            errors["base"] = "unknown"
            err_msg = str(err)

        except OSError as err:
            if err.errno == errno.ENETUNREACH:
                errors["base"] = "cannot_connect"
                err_msg = str(err)
            else:
                errors["base"] = "unknown"
                err_msg = str(err)

        else:
            await self.async_set_unique_id(device.mac.hex())
            if device.is_locked:
                return await self.async_step_unlock()
            return await self.async_step_finish()

        await self.async_set_unique_id(device.mac.hex())
        _LOGGER.error(
            "Failed to authenticate to the device at %s: %s", device.host[0], err_msg
        )
        return self.async_show_form(step_id="auth", errors=errors)

    async def async_step_reset(self, user_input=None, errors=None) -> FlowResult:
        """Guide the user to unlock the device manually.

        We are unable to authenticate because the device is locked.
        The user needs to open the LinknLink app and unlock the device.
        """
        device = self.device

        if user_input is None:
            return self.async_show_form(
                step_id="reset",
                errors=errors,
                description_placeholders={
                    "name": device.name,
                    "model": device.model,
                    "host": device.host[0],
                },
            )

        return await self.async_step_user(
            {CONF_HOST: device.host[0], CONF_TIMEOUT: device.timeout}
        )

    async def async_step_unlock(self, user_input=None) -> FlowResult:
        """Unlock the device.

        The authentication succeeded, but the device is locked.
        We can offer an unlock to prevent authorization errors.
        """
        device = self.device
        errors = {}

        if user_input is None:
            pass

        elif user_input["unlock"]:
            try:
                await self.hass.async_add_executor_job(device.set_lock, False)

            except NetworkTimeoutError as err:
                errors["base"] = "cannot_connect"
                err_msg = str(err)

            except LinknLinkException as err:
                errors["base"] = "unknown"
                err_msg = str(err)

            except OSError as err:
                if err.errno == errno.ENETUNREACH:
                    errors["base"] = "cannot_connect"
                    err_msg = str(err)
                else:
                    errors["base"] = "unknown"
                    err_msg = str(err)

            else:
                return await self.async_step_finish()

            _LOGGER.error(
                "Failed to unlock the device at %s: %s", device.host[0], err_msg
            )

        else:
            return await self.async_step_finish()

        data_schema = {vol.Required("unlock", default=False): bool}
        return self.async_show_form(
            step_id="unlock",
            errors=errors,
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "name": device.name,
                "model": device.model,
                "host": device.host[0],
            },
        )

    async def async_step_finish(self, user_input=None) -> FlowResult:
        """Choose a name for the device and create config entry."""
        device = self.device

        # Abort reauthentication flow.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: device.host[0], CONF_TIMEOUT: device.timeout}
        )

        return self.async_create_entry(
            title=f"{DOMAIN}-{device.model}",
            data={
                CONF_HOST: device.host[0],
                CONF_MAC: device.mac.hex(),
                CONF_TYPE: device.devtype,
                CONF_TIMEOUT: device.timeout,
            },
        )
