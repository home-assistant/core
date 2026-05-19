"""Config flow for the Glutz eAccess integration."""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pyglutz_eaccess import (
    GlutzAPI,
    GlutzAuthError,
    GlutzConnectionError,
    parse_invitation,
    resolve_instance_host,
    set_new_password,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

DEFAULT_TITLE = "Glutz eAccess"


def _is_valid_password(pwd: str) -> bool:
    """Return True if the password meets the Glutz cloud password policy."""
    return (
        len(pwd) >= 8
        and any(c.isupper() for c in pwd)
        and any(c.islower() for c in pwd)
        and any(c.isdigit() for c in pwd)
        and any(not c.isalnum() for c in pwd)
    )


STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_INVITATION_SCHEMA = vol.Schema({vol.Required("invite_url"): str})


def _invitation_confirm_schema(host: str, email: str) -> vol.Schema:
    """Build the invitation confirm schema with prefilled host and email."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_USERNAME, default=email): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


class GlutzConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Glutz eAccess."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._invitation: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the menu offering credentials or invitation entry points."""
        return self.async_show_menu(
            step_id="user", menu_options=["credentials", "invitation"]
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials login step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = GlutzAPI(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await api.get_access_points()
                info = await api.get_system_info()
            except GlutzAuthError:
                errors["base"] = "invalid_auth"
            except GlutzConnectionError:
                errors["base"] = "cannot_connect"
            else:
                system_id = info.get("id")
                if not system_id:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(system_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=info.get("name") or DEFAULT_TITLE, data=user_input
                    )

        return self.async_show_form(
            step_id="credentials", data_schema=STEP_CREDENTIALS_SCHEMA, errors=errors
        )

    async def async_step_invitation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the invitation URL step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parsed = parse_invitation(user_input["invite_url"])
            except ValueError:
                errors["base"] = "invalid_invitation"
            else:
                try:
                    host = await resolve_instance_host(
                        async_get_clientsession(self.hass),
                        parsed["cloud_host"],
                        parsed["system_path"],
                    )
                except GlutzConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    self._invitation = {
                        "host": host,
                        "email": parsed["email"],
                        "token": parsed["token"],
                    }
                    if system_id := parsed.get("system_id"):
                        self._invitation["system_id"] = system_id
                    return await self.async_step_invitation_confirm()

        return self.async_show_form(
            step_id="invitation", data_schema=STEP_INVITATION_SCHEMA, errors=errors
        )

    async def async_step_invitation_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setting the password and creating the entry from an invitation."""
        if self._invitation is None:
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        default_host = f"https://{self._invitation['host']}"
        default_email = self._invitation["email"]

        if user_input is not None:
            full_host = user_input[CONF_HOST]
            email = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            if not _is_valid_password(password):
                errors["base"] = "invalid_password"

            if not errors:
                if system_id := self._invitation.get("system_id"):
                    await self.async_set_unique_id(system_id)
                    self._abort_if_unique_id_configured()

                try:
                    await set_new_password(
                        async_get_clientsession(self.hass),
                        urlparse(full_host).netloc or full_host,
                        self._invitation["token"],
                        password,
                    )
                except GlutzAuthError:
                    errors["base"] = "invalid_auth"
                except GlutzConnectionError:
                    errors["base"] = "cannot_connect"

                if not errors:
                    api = GlutzAPI(
                        async_get_clientsession(self.hass), full_host, email, password
                    )
                    try:
                        await api.get_access_points()
                        info = await api.get_system_info()
                    except GlutzAuthError:
                        errors["base"] = "invalid_auth"
                    except GlutzConnectionError:
                        errors["base"] = "cannot_connect"
                    else:
                        system_id = info.get("id") or self._invitation.get("system_id")
                        if not system_id:
                            errors["base"] = "cannot_connect"
                        else:
                            if not self._invitation.get("system_id"):
                                await self.async_set_unique_id(system_id)
                                self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=info.get("name") or DEFAULT_TITLE,
                                data={
                                    CONF_HOST: full_host,
                                    CONF_USERNAME: email,
                                    CONF_PASSWORD: password,
                                },
                            )

        return self.async_show_form(
            step_id="invitation_confirm",
            data_schema=_invitation_confirm_schema(default_host, default_email),
            errors=errors,
        )
