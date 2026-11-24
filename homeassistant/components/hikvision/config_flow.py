"""Config flow for Hikvision integration."""

from collections.abc import Mapping
import logging
from typing import Any, override
import uuid

import probatio
from pyhik.hikvision import HikCamera
import requests

from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .const import CONF_RANDOM_ID, DEFAULT_PORT, DOMAIN
from .identity import is_made_up_id, is_random_id_made_up

_LOGGER = logging.getLogger(__name__)


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
                camera = await _async_connect(
                    self.hass, host, port, username, password, ssl, verify_ssl
                )
            except requests.exceptions.RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                device_id = camera.get_id
                device_name = camera.get_name
                if device_id is None:
                    errors["base"] = (
                        "invalid_auth" if camera.auth_failed else "cannot_connect"
                    )
                else:
                    # pyHik gives a UUID object for a device whose own ID it made up;
                    # a unique ID must be a string.
                    await self.async_set_unique_id(str(device_id))
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_name or host,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_SSL: ssl,
                            CONF_VERIFY_SSL: verify_ssl,
                            # Known only now: the ID is stored as a string.
                            CONF_RANDOM_ID: is_random_id_made_up(device_id),
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
                camera = await _async_connect(
                    self.hass,
                    reauth_entry.data[CONF_HOST],
                    reauth_entry.data[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    reauth_entry.data[CONF_SSL],
                    reauth_entry.data.get(CONF_VERIFY_SSL, True),
                )
            except requests.exceptions.RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if (device_id := camera.get_id) is None:
                    errors["base"] = (
                        "invalid_auth" if camera.auth_failed else "cannot_connect"
                    )
                else:
                    if not (
                        isinstance(device_id, uuid.UUID) and is_made_up_id(reauth_entry)
                    ):
                        await self.async_set_unique_id(str(device_id))
                        self._abort_if_unique_id_mismatch(reason="wrong_device")
                    if reauth_entry.state is ConfigEntryState.FAILED_UNLOAD:
                        # Home Assistant does not reload an entry whose unload
                        # failed: only a restart sets it up again, with the new
                        # credentials. Its stream was stopped when the password
                        # was rejected.
                        self.hass.config_entries.async_update_entry(
                            reauth_entry, data={**reauth_entry.data, **user_input}
                        )
                        return self.async_abort(reason="reauth_restart_required")
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
