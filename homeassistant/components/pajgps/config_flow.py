"""Config flow for PAJ GPS Tracker integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any
import uuid

from pajgps_api import PajGpsApi
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from . import PajGpsConfigEntry

_LOGGER = logging.getLogger(__name__)


def _build_config_schema(
    entry_name: str = "My Paj GPS Account",
    email: str = "",
    password: str = "",
    mark_alerts_as_read: bool = True,
    fetch_elevation: bool = False,
    force_battery: bool = False,
) -> vol.Schema:
    """Build config schema with optional pre-filled defaults."""
    return vol.Schema(
        {
            vol.Required("entry_name", default=entry_name): cv.string,
            vol.Required("email", default=email): cv.string,
            vol.Required("password", default=password): cv.string,
        }
    )


async def _validate_credentials(email: str, password: str) -> str | None:
    """Attempt a real login with the given credentials.

    Returns an error key string on failure, or None on success.
    """
    api: PajGpsApi | None = None
    try:
        api = PajGpsApi(email=email, password=password)
        await api.login()
    except (AuthenticationError, TokenRefreshError):
        return "invalid_auth"
    except Exception:  # noqa: BLE001
        return "cannot_connect"
    finally:
        if api is not None:
            try:
                await api.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error closing PajGpsApi session", exc_info=True)
    return None


class CustomFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for PAJ GPS Tracker."""

    data: dict[str, Any] | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input
            # Create new guid for the entry
            self.data["guid"] = str(uuid.uuid4())
            # If entry_name is null or empty string, add error
            if not self.data["entry_name"] or self.data["entry_name"] == "":
                errors["base"] = "entry_name_required"
            # If email is null or empty string, add error
            elif not self.data["email"] or self.data["email"] == "":
                errors["base"] = "email_required"
            # If password is null or empty string, add error
            elif not self.data["password"] or self.data["password"] == "":
                errors["base"] = "password_required"
            if not errors:
                self._async_abort_entries_match({"email": self.data["email"]})
                error_key = await _validate_credentials(
                    self.data["email"], self.data["password"]
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
                    email=user_input.get("email", ""),
                    password=user_input.get("password", ""),
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user", data_schema=_build_config_schema(), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication when credentials are invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication confirmation form."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            if not user_input.get("email"):
                errors["base"] = "email_required"
            elif not user_input.get("password"):
                errors["base"] = "password_required"
            else:
                error_key = await _validate_credentials(
                    user_input["email"], user_input["password"]
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
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            if not user_input.get("entry_name"):
                errors["base"] = "entry_name_required"
            elif not user_input.get("email"):
                errors["base"] = "email_required"
            elif not user_input.get("password"):
                errors["base"] = "password_required"
            else:
                error_key = await _validate_credentials(
                    user_input["email"], user_input["password"]
                )
                if error_key:
                    errors["base"] = error_key
                else:
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data={
                            **reconfigure_entry.data,
                            "entry_name": user_input["entry_name"],
                            "email": user_input["email"],
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
                    user_input.get("email") or ""
                    if user_input
                    else reconfigure_entry.data.get("email", "")
                ),
                password=(
                    user_input.get("password") or ""
                    if user_input
                    else reconfigure_entry.data.get("password", "")
                ),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: PajGpsConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: PajGpsConfigEntry) -> None:
        """Initialize the options flow handler."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        default_entry_name = ""
        if "entry_name" in self._config_entry.data:
            default_entry_name = self._config_entry.data["entry_name"]
        if "entry_name" in self._config_entry.options:
            default_entry_name = self._config_entry.options["entry_name"]
        default_email = ""
        if "email" in self._config_entry.data:
            default_email = self._config_entry.data["email"]
        if "email" in self._config_entry.options:
            default_email = self._config_entry.options["email"]
        default_password = ""
        if "password" in self._config_entry.data:
            default_password = self._config_entry.data["password"]
        if "password" in self._config_entry.options:
            default_password = self._config_entry.options["password"]

        if user_input is not None:
            # Validate required fields in priority order to avoid overwriting errors["base"]
            if not user_input.get("entry_name"):
                errors["base"] = "entry_name_required"
            elif not user_input.get("email"):
                errors["base"] = "email_required"
            elif not user_input.get("password"):
                errors["base"] = "password_required"
            if not errors:
                error_key = await _validate_credentials(
                    user_input["email"], user_input["password"]
                )
                if error_key:
                    errors["base"] = error_key
            if not errors:
                # Update the config entry with the new data and let the
                # _async_update_listener in __init__.py reload the coordinator.
                new_data = {
                    "guid": self._config_entry.data["guid"],
                    "entry_name": user_input["entry_name"],
                    "email": user_input["email"],
                    "password": user_input["password"],
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
