"""Config flow for Broadlink devices."""
import errno
from functools import partial
import socket

import broadlink as blk
from broadlink.exceptions import AuthenticationError, DeviceOfflineError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TIMEOUT, CONF_TYPE
from homeassistant.helpers import config_validation as cv

from . import LOGGER
from .const import (  # pylint: disable=unused-import
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)


class BroadlinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Broadlink config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Broadlink flow."""
        self.device = None

    async def async_set_device(self, device=None):
        """Define a device for the config flow."""
        if device is None:
            await self.async_set_unique_id()
            self.device = None
            return

        await self.async_set_unique_id(device.mac.hex())
        self.device = device

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "name": device.name or "Unknown",
            "model": device.model,
            "host": device.host[0],
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_hello()

    async def async_step_import(self, import_info):
        """Handle a flow initiated by an import."""
        mac_addr = import_info.get(CONF_MAC)

        if mac_addr is None:
            return await self.async_step_hello(import_info)

        host = import_info[CONF_HOST]
        mac_addr = bytes.fromhex(mac_addr)
        dev_type = import_info[CONF_TYPE]
        name = import_info.get(CONF_NAME)
        timeout = import_info.get(CONF_TIMEOUT)

        device = blk.gendevice(dev_type, (host, DEFAULT_PORT), mac_addr, name=name)
        device.timeout = timeout
        await self.async_set_device(device)
        return await self.async_step_auth()

    async def async_step_hello(self, device_info=None):
        """Start communicating with the device."""
        errors = {}

        if device_info is not None:
            host = device_info[CONF_HOST]
            timeout = device_info[CONF_TIMEOUT]

            try:
                hello = partial(blk.discover, discover_ip_address=host, timeout=timeout)
                device = (await self.hass.async_add_executor_job(hello))[0]

            except socket.gaierror:
                errors["base"] = "invalid_hostname"
                err_msg = "Invalid hostname"

            except OSError as err:
                if err.errno == errno.EINVAL:
                    errors["base"] = "invalid_ip_address"
                    err_msg = "Invalid IP address"
                else:
                    errors["base"] = "unknown_error"
                    err_msg = f"{type(err).__name__}: {err}"

            except IndexError:
                errors["base"] = "device_not_found"
                err_msg = "Device not found"

            except Exception as err:  # pylint: disable=broad-except
                errors["base"] = "unknown_error"
                err_msg = f"{type(err).__name__}: {err}"

            else:
                device.timeout = timeout
                await self.async_set_device(device)
                return await self.async_step_auth()

            LOGGER.error("Failed to discover the device at %s: %s", host, err_msg)

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        }
        return self.async_show_form(
            step_id="hello", data_schema=vol.Schema(data_schema), errors=errors,
        )

    async def async_step_auth(self):
        """Authenticate to the device."""
        device = self.device
        errors = {}

        try:
            await self.hass.async_add_executor_job(device.auth)

        except AuthenticationError:
            return await self.async_step_reset()

        except DeviceOfflineError as err:
            errors["base"] = "device_offline"
            err_msg = str(err)

        except Exception as err:  # pylint: disable=broad-except
            errors["base"] = "unknown_error"
            err_msg = f"{type(err).__name__}: {err}"

        else:
            if device.cloud:
                return await self.async_step_unlock()
            return await self.async_step_finish()

        LOGGER.error(
            "Failed to authenticate to the device at %s: %s", device.host[0], err_msg
        )
        return self.async_show_form(step_id="auth", errors=errors)

    async def async_step_reset(self, user_input=None):
        """Guide the user to unlock the device manually."""
        if user_input is None:
            return self.async_show_form(step_id="reset")

        await self.async_set_device()
        return await self.async_step_hello()

    async def async_step_unlock(self, user_input=None):
        """Unlock the device to prevent authorization errors."""
        device = self.device
        errors = {}

        if user_input is None:
            pass

        elif user_input["unlock"] is True:
            try:
                await self.hass.async_add_executor_job(device.set_lock, False)

            except DeviceOfflineError as err:
                errors["base"] = "device_offline"
                err_msg = str(err)

            except Exception as err:  # pylint: disable=broad-except
                errors["base"] = "unknown_error"
                err_msg = f"{type(err).__name__}: {err}"

            else:
                return await self.async_step_finish()

            LOGGER.error(
                "Failed to unlock the device at %s: %s", device.host[0], err_msg
            )

        else:
            return await self.async_step_finish()

        data_schema = {vol.Required("unlock", default=False): bool}
        return self.async_show_form(
            step_id="unlock", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_finish(self, user_input=None):
        """Choose a name for the device and create config entry."""
        device = self.device

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_HOST: device.host[0],
                    CONF_MAC: device.mac.hex(),
                    CONF_TYPE: device.devtype,
                    CONF_TIMEOUT: device.timeout,
                },
            )

        data_schema = {vol.Required(CONF_NAME, default=device.name): str}
        return self.async_show_form(
            step_id="finish", data_schema=vol.Schema(data_schema)
        )
