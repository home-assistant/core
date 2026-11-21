"""Config flow for Hikvision integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from pyhik.hikvision import HikCamera
import requests

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The password is not shown again: left empty, the stored one is kept.
RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT): int,
        probatio.Required(CONF_SSL): bool,
        probatio.Required(CONF_VERIFY_SSL): bool,
        probatio.Required(CONF_USERNAME): str,
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): str,
    }
)


async def _async_connect(
    hass: HomeAssistant,
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool,
    verify_ssl: bool,
) -> HikCamera:
    """Connect to a device and read its identity."""
    protocol = "https" if ssl else "http"
    return await hass.async_add_executor_job(
        HikCamera, f"{protocol}://{host}", port, username, password, verify_ssl
    )


class _CheckError(Exception):
    """The device could not be used, with the error to show."""

    def __init__(self, error: str) -> None:
        """Initialize the error."""
        super().__init__(error)
        self.error = error


async def _async_check_device(
    hass: HomeAssistant,
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool,
    verify_ssl: bool,
) -> HikCamera:
    """Connect to a device, and return it once it has shown its ID."""
    try:
        camera = await _async_connect(
            hass, host, port, username, password, ssl, verify_ssl
        )
    except requests.exceptions.RequestException as err:
        raise _CheckError("cannot_connect") from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise _CheckError("unknown") from err
    if camera.get_id is None:
        raise _CheckError("invalid_auth" if camera.auth_failed else "cannot_connect")
    return camera


class HikvisionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            ssl = user_input[CONF_SSL]
            verify_ssl = user_input[CONF_VERIFY_SSL]

            try:
                camera = await _async_check_device(
                    self.hass, host, port, username, password, ssl, verify_ssl
                )
            except _CheckError as err:
                errors["base"] = err.error
            else:
                await self.async_set_unique_id(camera.get_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=camera.get_name or host,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_SSL: ssl,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): str,
                    probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    probatio.Required(CONF_USERNAME): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                    probatio.Required(CONF_SSL, default=False): bool,
                    probatio.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the device rejecting the stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                camera = await _async_check_device(
                    self.hass,
                    reauth_entry.data[CONF_HOST],
                    reauth_entry.data[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    reauth_entry.data[CONF_SSL],
                    reauth_entry.data.get(CONF_VERIFY_SSL, True),
                )
            except _CheckError as err:
                errors["base"] = err.error
            else:
                await self.async_set_unique_id(camera.get_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=reauth_entry.data[CONF_USERNAME]
                    ): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            description_placeholders={"name": reauth_entry.title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a change of where and how the device is reached."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            # An empty password keeps the stored one.
            password = (
                user_input.get(CONF_PASSWORD) or reconfigure_entry.data[CONF_PASSWORD]
            )
            try:
                camera = await _async_check_device(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    password,
                    user_input[CONF_SSL],
                    user_input[CONF_VERIFY_SSL],
                )
            except _CheckError as err:
                errors["base"] = err.error
            else:
                await self.async_set_unique_id(camera.get_id)
                self._abort_if_unique_id_mismatch(reason="different_device")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={**user_input, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA,
                # Entries created before the option existed verify the certificate,
                # and the form must not show it as off.
                user_input
                or {
                    CONF_VERIFY_SSL: True,
                    **{
                        key: value
                        for key, value in reconfigure_entry.data.items()
                        if key != CONF_PASSWORD
                    },
                },
            ),
            description_placeholders={"name": reconfigure_entry.title},
            errors=errors,
        )
