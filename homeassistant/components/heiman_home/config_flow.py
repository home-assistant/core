"""Config flow to configure Heiman."""

import logging
from typing import Any

from heimanconnect import HeimanAuthError, HeimanHome, HeimanTokenExpiredError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .api import HeimanApiClient
from .const import CONF_HOME_ID, CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AuthInfo:
    """Store authentication info temporarily during config flow."""

    def __init__(self) -> None:
        """Initialize auth info."""
        self.homes: list[HeimanHome] = []
        self.user_info: Any = None
        self.auth_data: dict[str, Any] = {}


class HeimanConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle configuration of Heiman integration."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._auth_info = AuthInfo()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for Heiman."""
        api_client = HeimanApiClient(
            hass=self.hass, session=None, token_data=data[CONF_TOKEN]
        )

        try:
            await api_client.initialize()

            try:
                user_info = await api_client.cloud_client.async_get_user_info()
                homes = await api_client.cloud_client.async_get_homes()
                if not homes:
                    return self.async_abort(reason="no_homes")
            except HeimanTokenExpiredError:
                return self.async_abort(reason="token_expired")
            except HeimanAuthError:
                return self.async_abort(reason="token_invalid")
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to fetch account information: %s", err)
                return self.async_abort(reason="account_info_failed")

            self._auth_info.homes = homes if isinstance(homes, list) else []
            self._auth_info.user_info = user_info
            self._auth_info.auth_data = data

            return await self.async_step_select_home()
        finally:
            # Always close the temporary API client to prevent resource leaks
            await api_client.close()

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle home selection step."""
        if user_input is not None:
            selected_home_id = user_input.get(CONF_HOME_ID)

            if not selected_home_id:
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=self._get_home_selection_schema(),
                    errors={"base": "no_home_selected"},
                )

            await self.async_set_unique_id(self._auth_info.user_info.user_id)
            self._abort_if_unique_id_configured()

            config_data = {
                **self._auth_info.auth_data,
                CONF_HOME_ID: selected_home_id,
                CONF_USER_ID: self._auth_info.user_info.user_id,
            }

            # Use SDK method to get display name for better localization
            title = self._auth_info.user_info.get_display_name() or "Heiman Home"

            return self.async_create_entry(
                title=title,
                data=config_data,
            )

        # Check if all homes have invalid home_id before showing form
        schema = self._get_home_selection_schema()
        if not schema.schema:  # Empty schema means no valid homes
            _LOGGER.error(
                "All homes returned from API have invalid home_id; "
                "this indicates an API issue or data structure change"
            )
            return self.async_abort(reason="invalid_home_data")

        return self.async_show_form(
            step_id="select_home",
            data_schema=schema,
            description_placeholders={
                "user_email": self._auth_info.user_info.email or "User",
            },
        )

    def _get_home_selection_schema(self) -> vol.Schema:
        """Get home selection schema."""
        homes = self._auth_info.homes

        if not homes:
            return vol.Schema({})

        home_options = {}
        for home in homes:
            home_id = getattr(home, "home_id", "")
            if not home_id:
                continue
            home_name = getattr(home, "home_name", "Unknown")
            device_count = getattr(home, "device_count", 0)

            display_text = f"{home_name} [{device_count} devices]"
            home_options[home_id] = display_text

        if not home_options:
            # Return empty schema when no valid homes found
            # Caller should handle this case appropriately
            return vol.Schema({})

        return vol.Schema(
            {
                vol.Required(CONF_HOME_ID): vol.In(home_options),
            }
        )
