"""Config flow for Broadlink devices."""
import errno
from functools import partial
import socket

import broadlink as blk
from broadlink.exceptions import (
    AuthenticationError,
    BroadlinkException,
    DeviceOfflineError,
)
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
from .helpers import format_mac


class BroadlinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Broadlink config flow."""

    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    VERSION = 1

    def __init__(self):
        """Initialize the Broadlink flow."""
        self.device = None

    async def async_set_device(self, device, raise_on_progress=True):
        """Define a device for the config flow."""
        await self.async_set_unique_id(
            device.mac.hex(), raise_on_progress=raise_on_progress
        )
        self.device = device

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "name": device.name,
            "model": device.model,
            "host": device.host[0],
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

            try:
                hello = partial(blk.discover, discover_ip_address=host, timeout=timeout)
                device = (await self.hass.async_add_executor_job(hello))[0]

            except IndexError:
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
                device.timeout = timeout

                if self.unique_id is None:
                    await self.async_set_device(device)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: device.host[0], CONF_TIMEOUT: timeout}
                    )
                    return await self.async_step_auth()

                # The user came from a factory reset.
                # We need to check whether the host is correct.
                if device.mac == self.device.mac:
                    await self.async_set_device(device, raise_on_progress=False)
                    return await self.async_step_auth()

                errors["base"] = "invalid_host"
                err_msg = (
                    "Invalid host for this configuration flow. The MAC address should be "
                    f"{format_mac(self.device.mac)}, but {format_mac(device.mac)} was given"
                )

            LOGGER.error("Failed to connect to the device at %s: %s", host, err_msg)

            if self.source == config_entries.SOURCE_IMPORT:
                return self.async_abort(reason=errors["base"])

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        }
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors,
        )

    async def async_step_auth(self):
        """Authenticate to the device."""
        device = self.device
        errors = {}

        try:
            await self.hass.async_add_executor_job(device.auth)

        except AuthenticationError:
            errors["base"] = "invalid_auth"
            await self.async_set_unique_id(device.mac.hex())
            return await self.async_step_reset(errors=errors)

        except DeviceOfflineError as err:
            errors["base"] = "cannot_connect"
            err_msg = str(err)

        except BroadlinkException as err:
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
            if self.source == config_entries.SOURCE_IMPORT:
                LOGGER.warning(
                    "The %s at %s is ready to be configured. Please "
                    "click Configuration in the sidebar and click "
                    "Integrations. Then find the device there and click "
                    "Configure to finish the setup",
                    device.model,
                    device.host[0],
                )

            if device.is_locked:
                return await self.async_step_unlock()
            return await self.async_step_finish()

        await self.async_set_unique_id(device.mac.hex())
        LOGGER.error(
            "Failed to authenticate to the device at %s: %s", device.host[0], err_msg
        )
        return self.async_show_form(step_id="auth", errors=errors)

    async def async_step_reset(self, user_input=None, errors=None):
        """Guide the user to unlock the device manually.

        We are unable to authenticate because the device is locked.
        The user needs to factory reset the device to make it work
        with Home Assistant.
        """
        if user_input is None:
            return self.async_show_form(step_id="reset", errors=errors)

        return await self.async_step_user(
            {CONF_HOST: self.device.host[0], CONF_TIMEOUT: self.device.timeout}
        )

    async def async_step_unlock(self, user_input=None):
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

            except DeviceOfflineError as err:
                errors["base"] = "cannot_connect"
                err_msg = str(err)

            except BroadlinkException as err:
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
        errors = {}

        # Abort reauthentication flow.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: device.host[0], CONF_TIMEOUT: device.timeout}
        )

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
            step_id="finish", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_import(self, import_info):
        """Import a device."""
        if any(
            import_info[CONF_HOST] == entry.data[CONF_HOST]
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_info)

    async def async_step_reauth(self, data):
        """Reauthenticate to the device."""
        device = blk.gendevice(
            data[CONF_TYPE],
            (data[CONF_HOST], DEFAULT_PORT),
            bytes.fromhex(data[CONF_MAC]),
            name=data[CONF_NAME],
        )
        device.timeout = data[CONF_TIMEOUT]
        await self.async_set_device(device)
        return await self.async_step_reset()
