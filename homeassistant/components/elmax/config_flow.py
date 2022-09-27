"""Config flow for elmax-cloud integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError
from elmax_api.http import Elmax
from elmax_api.model.panel import PanelEntry
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

LOGIN_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_USERNAME): str,
        vol.Required(CONF_ELMAX_PASSWORD): str,
    }
)


def _store_panel_by_name(
    panel: PanelEntry, username: str, panel_names: dict[str, str]
) -> None:
    original_panel_name = panel.get_name_by_user(username=username)
    panel_id = panel.hash
    collisions_count = 0
    panel_name = original_panel_name
    while panel_name in panel_names:
        # Handle same-name collision.
        collisions_count += 1
        panel_name = f"{original_panel_name} ({collisions_count})"
    panel_names[panel_name] = panel_id


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for elmax-cloud."""

    VERSION = 1
    _client: Elmax
    _username: str
    _password: str
    _panels_schema: vol.Schema
    _panel_names: dict
    _reauth_username: str | None
    _reauth_panelid: str | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # When invokes without parameters, show the login form.
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=LOGIN_FORM_SCHEMA)

        username = user_input[CONF_ELMAX_USERNAME]
        password = user_input[CONF_ELMAX_PASSWORD]

        # Otherwise, it means we are handling now the "submission" of the user form.
        # In this case, let's try to log in to the Elmax cloud and retrieve the available panels.
        try:
            client = await self._async_login(username=username, password=password)

        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id="user",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except ElmaxNetworkError:
            _LOGGER.exception("A network error occurred")
            return self.async_show_form(
                step_id="user",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "network_error"},
            )

        # If the login succeeded, retrieve the list of available panels and filter the online ones
        online_panels = [x for x in await client.list_control_panels() if x.online]

        # If no online panel was found, we display an error in the next UI.
        if not online_panels:
            return self.async_show_form(
                step_id="user",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "no_panel_online"},
            )

        # Show the panel selection.
        # We want the user to choose the panel using the associated name, we set up a mapping
        # dictionary to handle that case.
        panel_names: dict[str, str] = {}
        username = client.get_authenticated_username()
        for panel in online_panels:
            _store_panel_by_name(
                panel=panel, username=username, panel_names=panel_names
            )

        self._client = client
        self._panel_names = panel_names
        schema = vol.Schema(
            {
                vol.Required(CONF_ELMAX_PANEL_NAME): vol.In(self._panel_names.keys()),
                vol.Required(CONF_ELMAX_PANEL_PIN, default="000000"): str,
            }
        )
        self._panels_schema = schema
        self._username = username
        self._password = password
        # If everything went OK, proceed to panel selection.
        return await self.async_step_panels(user_input=None)

    async def async_step_panels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Panel selection step."""
        errors: dict[str, Any] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="panels", data_schema=self._panels_schema, errors=errors
            )

        panel_name = user_input[CONF_ELMAX_PANEL_NAME]
        panel_pin = user_input[CONF_ELMAX_PANEL_PIN]

        # Lookup the panel id from the panel name.
        panel_id = self._panel_names[panel_name]

        # Make sure this is the only elmax integration for this specific panel id.
        await self.async_set_unique_id(panel_id)
        self._abort_if_unique_id_configured()

        # Try to list all the devices using the given PIN.
        try:
            await self._client.get_panel_status(
                control_panel_id=panel_id, pin=panel_pin
            )
            return self.async_create_entry(
                title=f"Elmax {panel_name}",
                data={
                    CONF_ELMAX_PANEL_ID: panel_id,
                    CONF_ELMAX_PANEL_PIN: panel_pin,
                    CONF_ELMAX_USERNAME: self._username,
                    CONF_ELMAX_PASSWORD: self._password,
                },
            )
        except ElmaxBadPinError:
            errors["base"] = "invalid_pin"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error occurred")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="panels", data_schema=self._panels_schema, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_username = entry_data.get(CONF_ELMAX_USERNAME)
        self._reauth_panelid = entry_data.get(CONF_ELMAX_PANEL_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauthorization flow."""
        errors = {}
        if user_input is not None:
            panel_pin = user_input.get(CONF_ELMAX_PANEL_PIN)
            password = user_input.get(CONF_ELMAX_PASSWORD)
            entry = await self.async_set_unique_id(self._reauth_panelid)

            # Handle authentication, make sure the panel we are re-authenticating against is listed among results
            # and verify its pin is correct.
            try:
                # Test login.
                client = await self._async_login(
                    username=self._reauth_username, password=password
                )

                # Make sure the panel we are authenticating to is still available.
                panels = [
                    p
                    for p in await client.list_control_panels()
                    if p.hash == self._reauth_panelid
                ]
                if len(panels) < 1:
                    raise NoOnlinePanelsError()

                # Verify the pin is still valid.from
                await client.get_panel_status(
                    control_panel_id=self._reauth_panelid, pin=panel_pin
                )

                # If it is, proceed with configuration update.
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_ELMAX_PANEL_ID: self._reauth_panelid,
                        CONF_ELMAX_PANEL_PIN: panel_pin,
                        CONF_ELMAX_USERNAME: self._reauth_username,
                        CONF_ELMAX_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                self._reauth_username = None
                self._reauth_panelid = None
                return self.async_abort(reason="reauth_successful")

            except ElmaxBadLoginError:
                _LOGGER.error(
                    "Wrong credentials or failed login while re-authenticating"
                )
                errors["base"] = "invalid_auth"
            except NoOnlinePanelsError:
                _LOGGER.warning(
                    "Panel ID %s is no longer associated to this user",
                    self._reauth_panelid,
                )
                errors["base"] = "reauth_panel_disappeared"
            except ElmaxBadPinError:
                errors["base"] = "invalid_pin"

        # We want the user to re-authenticate only for the given panel id using the same login.
        # We pin them to the UI, so the user realizes she must log in with the appropriate credentials
        # for the that specific panel.
        schema = vol.Schema(
            {
                vol.Required(CONF_ELMAX_USERNAME): self._reauth_username,
                vol.Required(CONF_ELMAX_PASSWORD): str,
                vol.Required(CONF_ELMAX_PANEL_ID): self._reauth_panelid,
                vol.Required(CONF_ELMAX_PANEL_PIN): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    async def _async_login(username: str, password: str) -> Elmax:
        """Log in to the Elmax cloud and return the http client."""
        client = Elmax(username=username, password=password)
        await client.login()
        return client


class NoOnlinePanelsError(HomeAssistantError):
    """Error occurring when no online panel was found."""
