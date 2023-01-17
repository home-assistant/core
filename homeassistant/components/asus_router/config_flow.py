"""Asus Router configuration flow module."""

from __future__ import annotations

import logging
import socket
from typing import Any

from asusrouter import (
    AsusRouterConnectionError,
    AsusRouterLoginBlockError,
    AsusRouterLoginError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .bridge import ARBridge
from .const import (
    BASE,
    CONF_DEFAULT_PORT,
    CONF_DEFAULT_SSL,
    CONF_DEFAULT_USERNAME,
    CONFIGS,
    DOMAIN,
    ERRORS,
    METHOD,
    NEXT,
    RESULT_CANNOT_RESOLVE,
    RESULT_CONNECTION_REFUSED,
    RESULT_ERROR,
    RESULT_LOGIN_BLOCKED,
    RESULT_SUCCESS,
    RESULT_UNKNOWN,
    RESULT_WRONG_CREDENTIALS,
    STEP_CREDENTIALS,
    STEP_FIND,
    STEP_FINISH,
    UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


def _check_host(
    host: str,
) -> str | None:
    """Get the IP address for the hostname."""

    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def _check_errors(
    errors: dict[str, Any] | None = None,
) -> bool:
    """Check for errors."""

    if errors is None:
        return False

    if BASE in errors and errors[BASE] != RESULT_SUCCESS and errors[BASE] != "":
        return True

    return False


async def _async_check_connection(
    hass: HomeAssistant,
    configs: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check connection to the device with provided configurations."""

    configs_to_use = configs.copy()
    if options:
        configs_to_use.update(options)
    if CONF_HOST not in configs_to_use:
        return {
            ERRORS: RESULT_ERROR,
        }
    host = configs_to_use[CONF_HOST]

    result = {}
    _LOGGER.debug("Setup initiated")

    # Initialize bridge
    bridge = ARBridge(hass, configs_to_use)

    # Connect
    try:
        await bridge.async_connect()
    # Credentials error
    except AsusRouterLoginError:
        _LOGGER.error("Error during connection to '%s'. Wrong credentials", host)
        return {
            ERRORS: RESULT_WRONG_CREDENTIALS,
        }
    # Login blocked by the device
    except AsusRouterLoginBlockError as ex:
        _LOGGER.error(
            "Device '%s' has reported block for the login (to many wrong attempts were made). \
                Please try again in %s seconds",
            host,
            ex.timeout,
        )
        return {
            ERRORS: RESULT_LOGIN_BLOCKED,
        }
    # Connection refused
    except AsusRouterConnectionError as ex:
        _LOGGER.error(
            "Connection refused by `%s`. Check SSL and port settings. Original exception: %s",
            host,
            ex,
        )
        return {
            ERRORS: RESULT_CONNECTION_REFUSED,
        }
    # Anything else
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error(
            "Unknown error of type '%s' during connection to `%s`: %s",
            type(ex),
            host,
            ex,
        )
        return {
            ERRORS: RESULT_UNKNOWN,
        }
    # Cleanup, so no unclosed sessions will be reported
    finally:
        await bridge.async_clean()

    # Serial number of the device is the best unique_id
    # API provides it all the time for all the devices.
    # MAC as an alternative might not be used / found on some
    # older devices and some Merlin-builds of FW
    result[UNIQUE_ID] = bridge.identity.serial
    await bridge.async_disconnect()
    for item in configs:
        configs_to_use.pop(item)

    result[CONFIGS] = configs_to_use

    _LOGGER.debug("Setup successful")

    return result


async def _async_process_step(
    steps: dict[str, dict[str, Any]],
    step: str | None = None,
    errors: dict[str, Any] | None = None,
    redirect: bool = False,
) -> FlowResult:
    """Universal step selector.

    When the name of the last step is provided, the next step is initialized.
    On errors the same step will repeat.
    """

    if step and step in steps:
        # Method description
        description = steps[step]
        # On errors or redirect, run the step method
        if _check_errors(errors) or redirect:
            if METHOD in description:
                return await description[METHOD]()
            raise ValueError(f"Step `{step}` is not properly defined")
        # If the next step is defined, move to it
        if NEXT in description and description[NEXT]:
            return await _async_process_step(steps, description[NEXT], redirect=True)
        raise ValueError(f"Step `{step}` is not properly defined")
    raise ValueError(f"Step `{step}` cannot be found")


# FORMS -->


def _create_form_find(
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Create a form for the 'find' step."""

    if not user_input:
        user_input = {}

    schema = {
        vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): cv.string,
    }

    return vol.Schema(schema)


def _create_form_credentials(
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Create a form for the 'credentials' step."""

    if not user_input:
        user_input = {}

    schema = {
        vol.Required(
            CONF_USERNAME, default=user_input.get(CONF_USERNAME, CONF_DEFAULT_USERNAME)
        ): cv.string,
        vol.Required(
            CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
        ): cv.string,
        vol.Optional(
            CONF_PORT, default=user_input.get(CONF_PORT, CONF_DEFAULT_PORT)
        ): cv.positive_int,
        vol.Optional(
            CONF_SSL, default=user_input.get(CONF_SSL, CONF_DEFAULT_SSL)
        ): cv.boolean,
    }

    return vol.Schema(schema)


# <-- FORMS


class ARFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Asus Router."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""

        self._configs: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._unique_id: str | None = None

        # Steps description
        self._steps: dict[str, dict[str, Any]] = {
            STEP_FIND: {METHOD: self.async_step_find, NEXT: STEP_CREDENTIALS},
            STEP_CREDENTIALS: {
                METHOD: self.async_step_credentials,
                NEXT: STEP_FINISH,
            },
            STEP_FINISH: {METHOD: self.async_step_finish},
        }

    # User setup
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Start configuration flow initiated by user."""

        return await self.async_step_find(user_input)

    # Step #1 - find the device
    async def async_step_find(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Find the device step."""

        step_id = STEP_FIND

        errors = {}

        if user_input:
            # Check if host can be resolved
            ip = await self.hass.async_add_executor_job(
                _check_host, user_input[CONF_HOST]
            )
            if not ip:
                errors[BASE] = RESULT_CANNOT_RESOLVE

            if not errors:
                # Save host to configs
                self._configs.update(user_input)
                # Proceed to the next step
                return await _async_process_step(self._steps, step_id, errors)

        user_input = {}

        return self.async_show_form(
            step_id=step_id,
            data_schema=_create_form_find(user_input),
            errors=errors,
        )

    # Step #2 - credentials and SSL
    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Credentials step."""

        step_id = STEP_CREDENTIALS

        errors = {}

        if user_input:
            # Check credentials and connection
            result = await _async_check_connection(self.hass, self._configs, user_input)
            # Show errors if any
            if ERRORS in result:
                errors[BASE] = result[ERRORS]
            else:
                # Saved the checked settings to the options
                self._options.update(result[CONFIGS])
                # Set unique ID obtained from the device during the check
                await self.async_set_unique_id(result[UNIQUE_ID])
                # Proceed to the next step
                return await _async_process_step(self._steps, step_id)

        user_input = self._options.copy()

        return self.async_show_form(
            step_id=step_id,
            data_schema=_create_form_credentials(user_input),
            errors=errors,
        )

    # Step Finish
    async def async_step_finish(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Finish setup."""

        return self.async_create_entry(
            title=self._configs[CONF_HOST],
            data=self._configs,
            options=self._options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow."""

        return AROptionsFlowHandler(config_entry)


class AROptionsFlowHandler(OptionsFlow):
    """Options flow for AsusRouter."""

    def __init__(
        self,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize options flow."""

        self.config_entry = config_entry

        self._configs: dict[str, Any] = self.config_entry.data.copy()
        self._host: str = self._configs[CONF_HOST]
        self._options: dict[str, Any] = self.config_entry.options.copy()

        # Dictionary last_step: next_step
        self._steps: dict[str, dict[str, Any]] = {
            STEP_CREDENTIALS: {
                METHOD: self.async_step_credentials,
                NEXT: STEP_FINISH,
            },
            STEP_FINISH: {METHOD: self.async_step_finish},
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Options flow."""

        return await self.async_step_credentials(user_input)

    # Step #1 - credentials and SSL
    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Credentials step."""

        step_id = STEP_CREDENTIALS

        errors = {}

        if user_input:
            self._options.update(user_input)
            result = await _async_check_connection(
                self.hass, self._configs, self._options
            )
            if ERRORS in result:
                errors[BASE] = result[ERRORS]
            else:
                self._options.update(result[CONFIGS])
                return await _async_process_step(self._steps, step_id, errors)

        user_input = self._options.copy()

        return self.async_show_form(
            step_id=step_id,
            data_schema=_create_form_credentials(user_input),
            errors=errors,
        )

    # Step Finish
    async def async_step_finish(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Finish setup."""

        return self.async_create_entry(
            title=self.config_entry.title,
            data=self._options,
        )
