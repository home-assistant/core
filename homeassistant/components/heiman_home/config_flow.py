"""Config flow to configure Heiman."""

from collections.abc import Mapping
import logging
from typing import Any

from heimanconnect import HeimanAuthError, HeimanHome, HeimanTokenExpiredError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
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
        # Create API client to validate token and get user info
        api_client = HeimanApiClient(
            hass=self.hass, session=None, token_data=data[CONF_TOKEN]
        )

        try:
            # Initialize the client before using cloud_client
            await api_client._ensure_initialized()  # noqa: SLF001

            # Get user info
            try:
                user_info = await api_client.cloud_client.async_get_user_info()
            except HeimanTokenExpiredError:
                return self.async_abort(reason="token_expired")
            except HeimanAuthError:
                return self.async_abort(reason="token_invalid")
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to get user info: %s", err)
                return self.async_abort(reason="user_info_failed")

            # Get home info
            try:
                homes = await api_client.cloud_client.async_get_homes()
                if not homes:
                    return self.async_abort(reason="no_homes")
            except HeimanTokenExpiredError:
                return self.async_abort(reason="token_expired")
            except HeimanAuthError:
                return self.async_abort(reason="token_invalid")
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Failed to get homes: %s", err)
                return self.async_abort(reason="homes_fetch_failed")

            # Store temporary data for home selection
            self._auth_info.homes = homes if isinstance(homes, list) else []
            self._auth_info.user_info = user_info
            self._auth_info.auth_data = data

            # Check if this is a re-authentication flow
            if self.source == SOURCE_REAUTH:
                # For re-auth, use existing home_id from the entry being re-authenticated
                reauth_entry = self._get_reauth_entry()
                config_data = {
                    **data,
                    CONF_HOME_ID: reauth_entry.data.get(CONF_HOME_ID),
                    CONF_USER_ID: user_info.user_id,
                }

                # Get title from user info (nick_name or email)
                title = (
                    getattr(user_info, "nick_name", None)
                    or getattr(user_info, "email", None)
                    or "Heiman Home"
                )

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=config_data,
                    title=title,
                )

            # Enter home selection step for new entries
            return await self.async_step_select_home()
        finally:
            # Always close the temporary API client to prevent resource leaks
            await api_client.close()

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle home selection step."""
        if user_input is not None:
            # User selected a home
            selected_home_id = user_input.get(CONF_HOME_ID)

            if not selected_home_id:
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=self._get_home_selection_schema(),
                    errors={"base": "no_home_selected"},
                )

            await self.async_set_unique_id(self._auth_info.user_info.user_id)
            self._abort_if_unique_id_configured()

            # Build config data with single home ID
            config_data = {
                **self._auth_info.auth_data,
                CONF_HOME_ID: selected_home_id,
                CONF_USER_ID: self._auth_info.user_info.user_id,
            }

            # Get title from user info (nick_name or email)
            user_info = self._auth_info.user_info
            title = (
                getattr(user_info, "nick_name", None)
                or getattr(user_info, "email", None)
                or "Heiman Home"
            )

            return self.async_create_entry(
                title=title,
                data=config_data,
            )

        # Show home selection form
        return self.async_show_form(
            step_id="select_home",
            data_schema=self._get_home_selection_schema(),
            description_placeholders={
                "user_email": getattr(self._auth_info.user_info, "email", None)
                or "User",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        if user_input is not None:
            # User confirmed re-authentication, start OAuth flow
            return await self.async_step_pick_implementation()

        reauth_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "name": reauth_entry.title,
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
            return vol.Schema({})

        return vol.Schema(
            {
                vol.Required(CONF_HOME_ID): vol.In(home_options),
            }
        )
