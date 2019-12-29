"""Config flow to configure the Home Panel integration."""
import logging

from homepanelapi.api import HomePanelApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.home_panel.const import DOMAIN
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class HomePanelFlowHandler(ConfigFlow):
    """Handle a Home Panel config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _hassio_discovery = None

    def __init__(self):
        """Initialize Home Panel flow."""
        pass

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=8234): vol.Coerce(int),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=True): bool,
                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(self, errors=None):
        """Show the Hass.io confirmation form to the user."""
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            data_schema=vol.Schema({}),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form(user_input)

        home_panel_api = HomePanelApi(
            user_input.get(CONF_HOST),
            user_input.get(CONF_PORT),
            user_input.get(CONF_SSL),
        )
        authenticated = await home_panel_api.async_authenticate(
            user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
        )
        if not authenticated:
            _LOGGER.error("Could not authenticate with Home Panel.")
            return False

        return self.async_create_entry(
            title=user_input.get(CONF_HOST),
            data={
                CONF_HOST: user_input.get(CONF_HOST),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_PORT: user_input.get(CONF_PORT),
                CONF_SSL: user_input.get(CONF_SSL),
                CONF_USERNAME: user_input.get(CONF_USERNAME),
            },
        )

    async def async_step_hassio(self, user_input=None):
        """Prepare configuration for a Hass.io Home Panel add-on.

        This flow is triggered by the discovery component.
        """
        entries = self._async_current_entries()

        if not entries:
            self._hassio_discovery = user_input
            return await self.async_step_hassio_confirm()

        cur_entry = entries[0]

        if (
            cur_entry.data[CONF_HOST] == user_input[CONF_HOST]
            and cur_entry.data[CONF_PORT] == user_input[CONF_PORT]
        ):
            return self.async_abort(reason="single_instance_allowed")

        is_loaded = cur_entry.state == config_entries.ENTRY_STATE_LOADED

        if is_loaded:
            await self.hass.config_entries.async_unload(cur_entry.entry_id)

        self.hass.config_entries.async_update_entry(
            cur_entry,
            data={
                **cur_entry.data,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            },
        )

        if is_loaded:
            await self.hass.config_entries.async_setup(cur_entry.entry_id)

        return self.async_abort(reason="existing_instance_updated")

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm Hass.io discovery."""
        if user_input is None:
            return await self._show_hassio_form()

        home_panel_api = HomePanelApi(
            user_input.get(CONF_HOST),
            user_input.get(CONF_PORT),
            user_input.get(CONF_SSL),
        )
        authenticated = await home_panel_api.async_authenticate(
            user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
        )
        if not authenticated:
            _LOGGER.error("Could not authenticate with Home Panel.")
            return False

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={
                CONF_HOST: user_input.get(CONF_HOST),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_PORT: user_input.get(CONF_PORT),
                CONF_SSL: user_input.get(CONF_SSL),
                CONF_USERNAME: user_input.get(CONF_USERNAME),
            },
        )
