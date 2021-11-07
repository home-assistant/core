"""Config flow for elmax-cloud integration."""
from __future__ import annotations

import logging
from typing import Any

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError
from elmax_api.http import Elmax
from elmax_api.model.panel import PanelEntry
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.elmax.const import (
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

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
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._client: Elmax = None
        self._username: str = None
        self._password: str = None
        self._panels_schema = None
        self._panel_names = None

    @callback
    def _async_current_entries(
        self, include_ignore: bool | None = None
    ) -> list[ConfigEntry]:
        """Return current entries.

        If the flow is user initiated, filter out ignored entries unless include_ignore is True.
        """
        config_entries = self.hass.config_entries.async_entries(self.handler)

        if (
            include_ignore is True
            or include_ignore is None
            and self.source != SOURCE_USER
        ):
            return config_entries

        return [entry for entry in config_entries if entry.source != SOURCE_IGNORE]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        # When invokes without parameters, show the login form.
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=LOGIN_FORM_SCHEMA)

        errors: dict[str, str] = {}
        username = user_input[CONF_ELMAX_USERNAME]
        password = user_input[CONF_ELMAX_PASSWORD]

        # Otherwise, it means we are handling now the "submission" of the user form.
        # In this case, let's try to login to the Elmax cloud and retrieve the available panels.
        try:
            client = Elmax(username=username, password=password)
            await client.login()

            # If the login succeeded, retrieve the list of available panels.
            panels = await client.list_control_panels()

            # Filter the online panels
            online_panels = filter(lambda x: x.online, panels)

            # If no online panel was found, we display an error in the next UI.
            panels = list(online_panels)
            if len(panels) < 1:
                raise NoOnlinePanelsError()

            # Show the panel selection.
            # We want the user to chose the panel using the associated name, we we set-up a mapping
            # dictionary to handle that case.
            panel_names: dict[str, str] = {}
            username = client.get_authenticated_username()
            for panel in panels:
                _store_panel_by_name(
                    panel=panel, username=username, panel_names=panel_names
                )

            self._client = client
            self._panel_names = panel_names
            schema = vol.Schema(
                {
                    vol.Required(CONF_ELMAX_PANEL_NAME): vol.In(
                        self._panel_names.keys()
                    ),
                    vol.Required(CONF_ELMAX_PANEL_PIN, default="000000"): str,
                }
            )
            self._panels_schema = schema
            self._username = username
            self._password = password
            return self.async_show_form(
                step_id="panels", data_schema=schema, errors=errors
            )

        except ElmaxBadLoginError:
            _LOGGER.error("Wrong credentials or failed login")
            errors["base"] = "bad_auth"
        except NoOnlinePanelsError:
            _LOGGER.warning("No online device panel was found")
            errors["base"] = "no_panel_online"
        except ElmaxNetworkError:
            _LOGGER.exception("A network error occurred")
            errors["base"] = "network_error"

        # If an error occurred, show back the login form.
        return self.async_show_form(
            step_id="user", data_schema=LOGIN_FORM_SCHEMA, errors=errors
        )

    async def async_step_panels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Panel selection step."""
        if user_input is None:
            # In in any case this step is invoked without any parameter, just restart the user step.
            return self.async_show_form(step_id="user", data_schema=LOGIN_FORM_SCHEMA)

        errors = {}
        panel_name = user_input.get(CONF_ELMAX_PANEL_NAME)
        panel_pin = user_input.get(CONF_ELMAX_PANEL_PIN)

        # Lookup the panel id from the panel name.
        panel_id = self._panel_names[panel_name]

        # Make sure this is the only elmax integration for this specific panel id.
        current_entries = self._async_current_entries()
        for entry in current_entries:
            if entry.data["panel_id"] == panel_id:
                _LOGGER.error(
                    "An Elmax integration has been already set up for panel %s",
                    panel_id,
                )
                return self.async_abort(reason="single_instance_allowed")

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
        except Exception:
            _LOGGER.exception("Error occurred")
            errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="panels", data_schema=self._panels_schema, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauthorization flow."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=LOGIN_FORM_SCHEMA)


class NoOnlinePanelsError(HomeAssistantError):
    """Error occurring when no online panel was found."""

    pass
