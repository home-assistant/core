"""Config flow for Hikvision integration."""

from collections.abc import Mapping
import logging
from typing import Any, override
import uuid

import probatio
from pyhik.hikvision import HikCamera
import requests

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_RANDOM_ID, DEFAULT_PORT, DOMAIN
from .identity import is_made_up_id, is_random_id_made_up

_LOGGER = logging.getLogger(__name__)

PORT = probatio.All(int, probatio.Range(min=1, max=65535))
PASSWORD = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

# The password is not shown again: left empty, the stored one is kept.
RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT): PORT,
        probatio.Required(CONF_SSL): bool,
        probatio.Required(CONF_VERIFY_SSL): bool,
        probatio.Required(CONF_USERNAME): str,
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): PASSWORD,
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
) -> str | uuid.UUID:
    """Connect to a device, and return its ID once it has shown it.

    pyHik gives a UUID object for a device whose own ID it made up.
    """
    try:
        camera = await _async_connect(
            hass, host, port, username, password, ssl, verify_ssl
        )
    except requests.exceptions.RequestException as err:
        raise _CheckError("cannot_connect") from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise _CheckError("unknown") from err
    if (device_id := camera.get_id) is None:
        raise _CheckError("invalid_auth" if camera.auth_failed else "cannot_connect")
    return device_id


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
                    # A unique ID must be a string.
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
                    probatio.Required(CONF_PORT, default=DEFAULT_PORT): PORT,
                    probatio.Required(CONF_USERNAME): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD,
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
                device_id = await _async_check_device(
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
                await self._async_check_same_device(
                    reauth_entry, device_id, "wrong_device"
                )
                return self._async_update_and_reload(
                    reauth_entry, user_input, "reauth_restart_required"
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=reauth_entry.data[CONF_USERNAME]
                    ): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD,
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

        if (
            user_input is not None
            and not user_input.get(CONF_PASSWORD)
            and (user_input[CONF_USERNAME] != reconfigure_entry.data[CONF_USERNAME])
        ):
            # The stored password is another user's.
            errors[CONF_PASSWORD] = "password_required"
        elif user_input is not None:
            # An empty password keeps the stored one.
            password = (
                user_input.get(CONF_PASSWORD) or reconfigure_entry.data[CONF_PASSWORD]
            )
            try:
                device_id = await _async_check_device(
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
                await self._async_check_same_device(
                    reconfigure_entry, device_id, "different_device"
                )
                return self._async_update_and_reload(
                    reconfigure_entry,
                    {**user_input, CONF_PASSWORD: password},
                    "reconfigure_restart_required",
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

    async def _async_check_same_device(
        self, entry: ConfigEntry, device_id: str | uuid.UUID, reason: str
    ) -> None:
        """Abort if the device is not the one the entry was set up for.

        A device whose ID pyHik makes up gets a new one each time, so an entry with
        a made-up ID cannot be checked against it.
        """
        if isinstance(device_id, uuid.UUID) and is_made_up_id(entry):
            return
        await self.async_set_unique_id(str(device_id))
        self._abort_if_unique_id_mismatch(reason=reason)

    def _async_update_and_reload(
        self, entry: ConfigEntry, data_updates: dict[str, Any], restart_reason: str
    ) -> ConfigFlowResult:
        """Save the new data, and reload the entry with it.

        Home Assistant does not reload an entry whose unload failed: only a restart
        sets it up again, with the new data, so the flow says so instead. A stream
        that was sending a rejected password was stopped when it was rejected.
        """
        if entry.state is ConfigEntryState.FAILED_UNLOAD:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, **data_updates}
            )
            return self.async_abort(reason=restart_reason)
        return self.async_update_reload_and_abort(entry, data_updates=data_updates)
