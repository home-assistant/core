"""Config flow for PAJ GPS Tracker integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any
import uuid

from pajgps_api import PajGpsApi
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from . import PajGpsConfigEntry

_LOGGER = logging.getLogger(__name__)


def _build_config_schema(
    entry_name: str = "My Paj GPS Account",
    email: str = "",
    password: str = "",
) -> vol.Schema:
    """Build config schema with optional pre-filled defaults."""
    return vol.Schema(
        {
            vol.Required("entry_name", default=entry_name): cv.string,
            vol.Required(CONF_EMAIL, default=email): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
        }
    )


def _build_options_schema(
    entry_name: str = "",
) -> vol.Schema:
    """Build options schema without password (credentials managed via reconfigure/reauth)."""
    return vol.Schema(
        {
            vol.Required("entry_name", default=entry_name): cv.string,
        }
    )


async def _validate_credentials(
    email: str, password: str, hass: HomeAssistant
) -> str | None:
    """Attempt a real login with the given credentials.

    Returns an error key string on failure, or None on success.
    """
    websession = async_get_clientsession(hass)
    api: PajGpsApi | None = None
    try:
        api = PajGpsApi(email=email, password=password, websession=websession)
        await api.login()
    except AuthenticationError, TokenRefreshError:
        return "invalid_auth"
    except Exception:  # noqa: BLE001
        return "cannot_connect"

    return None


class PajGPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for PAJ GPS Tracker."""

    data: dict[str, Any] | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input
            # Create new guid for the entry
            self.data["guid"] = str(uuid.uuid4())
            if not errors:
                # Normalize email for duplicate protection and storage
                normalized_email = self.data["email"].strip().lower()
                self.data[CONF_EMAIL] = normalized_email
                self._async_abort_entries_match({CONF_EMAIL: normalized_email})
                error_key = await _validate_credentials(
                    self.data[CONF_EMAIL], self.data[CONF_PASSWORD], self.hass
                )
                if error_key:
                    errors["base"] = error_key
            if not errors:
                return self.async_create_entry(
                    title=f"{self.data['entry_name']}", data=self.data
                )

            return self.async_show_form(
                step_id="user",
                data_schema=_build_config_schema(
                    entry_name=user_input.get("entry_name", ""),
                    email=user_input.get(CONF_EMAIL, ""),
                    password=user_input.get(CONF_PASSWORD, ""),
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user", data_schema=_build_config_schema(), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when credentials are invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation form."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            if not user_input.get(CONF_EMAIL):
                errors["base"] = "email_required"
            elif not user_input.get(CONF_PASSWORD):
                errors["base"] = "password_required"
            else:
                error_key = await _validate_credentials(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD], self.hass
                )
                if error_key:
                    errors["base"] = error_key
                else:
                    self.hass.config_entries.async_update_entry(
                        reauth_entry,
                        data={**reauth_entry.data, **user_input},
                    )
                    await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "email", default=reauth_entry.data.get("email", "")
                    ): cv.string,
                    vol.Required("password"): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            if not user_input.get("entry_name"):
                errors["base"] = "entry_name_required"
            elif not user_input.get(CONF_EMAIL):
                errors["base"] = "email_required"
            elif not user_input.get(CONF_PASSWORD):
                errors["base"] = "password_required"
            else:
                # Prevent changing to an email that is already configured
                email = user_input[CONF_EMAIL]
                if any(
                    entry.entry_id != reconfigure_entry.entry_id
                    and entry.data.get(CONF_EMAIL) == email
                    for entry in self._async_current_entries()
                ):
                    errors["base"] = "already_configured"
                else:
                    error_key = await _validate_credentials(
                        email, user_input[CONF_PASSWORD], self.hass
                    )
                    if error_key:
                        errors["base"] = error_key
                    else:
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            data={
                                **reconfigure_entry.data,
                                "entry_name": user_input["entry_name"],
                                "email": email,
                                "password": user_input["password"],
                            },
                            title=user_input["entry_name"],
                        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_config_schema(
                entry_name=(
                    user_input.get("entry_name") or ""
                    if user_input
                    else reconfigure_entry.data.get("entry_name", "")
                ),
                email=(
                    user_input.get(CONF_EMAIL) or ""
                    if user_input
                    else reconfigure_entry.data.get(CONF_EMAIL, "")
                ),
                password=(
                    user_input.get(CONF_PASSWORD) or ""
                    if user_input
                    else reconfigure_entry.data.get(CONF_PASSWORD, "")
                ),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: PajGpsConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: PajGpsConfigEntry) -> None:
        """Initialize the options flow handler."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        default_entry_name = self._config_entry.options.get(
            "entry_name", self._config_entry.data.get("entry_name", "")
        )
        default_email = self._config_entry.options.get(
            "email", self._config_entry.data.get("email", "")
        )
        default_password = self._config_entry.options.get(
            "password", self._config_entry.data.get("password", "")
        )

        if user_input is not None:
            if not user_input.get("entry_name"):
                errors["base"] = "entry_name_required"
            elif not user_input.get(CONF_EMAIL):
                errors["base"] = "email_required"
            elif not user_input.get(CONF_PASSWORD):
                errors["base"] = "password_required"
            if not errors:
                email = user_input[CONF_EMAIL]
                if any(
                    entry.entry_id != self._config_entry.entry_id
                    and entry.data.get(CONF_EMAIL) == email
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                ):
                    errors["base"] = "already_configured"
            if not errors:
                error_key = await _validate_credentials(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD], self.hass
                )
                if error_key:
                    errors["base"] = error_key
            if not errors:
                new_data = {
                    "guid": self._config_entry.data["guid"],
                    "entry_name": user_input["entry_name"],
                    "email": user_input[CONF_EMAIL],
                    "password": user_input[CONF_PASSWORD],
                }
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=new_data,
                    title=new_data["entry_name"],
                )
                return self.async_create_entry(
                    title=new_data["entry_name"], data=new_data
                )

            return self.async_show_form(
                step_id="init",
                data_schema=_build_config_schema(
                    entry_name=user_input.get("entry_name", default_entry_name),
                    email=user_input.get("email", default_email),
                    password=user_input.get("password", default_password),
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_config_schema(
                entry_name=default_entry_name,
                email=default_email,
                password=default_password,
            ),
            errors=errors,
        )
