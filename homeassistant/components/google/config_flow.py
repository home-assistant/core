"""Config flow for the Google component."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    LocalOAuth2Implementation,
)

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    DOMAIN,
    GOOGLE_APIS,
    GOOGLE_CALENDAR_API,
    GOOGLE_PEOPLE_API,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class GoogleLocalOAuth2Implementation(LocalOAuth2Implementation):
    """Google Local OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
    ):
        """Initialize local auth implementation."""
        self.hass = hass
        self._domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.scopes = []
        self._name = "APIs & Services"

        super().__init__(
            hass, domain, client_id, client_secret, authorize_url, token_url
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._name

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        extra = {
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
        return extra


async def is_valid(user_input):
    """Validate user input"""
    # TODO: Validate Client ID and Client Secret
    return True


class GoogleOAuth2ConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle OAuth2 config flow."""

    VERSION = 1
    DOMAIN = DOMAIN
    # TODO: Update this to CONN_CLASS_CLOUD_PUSH
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return a logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}
        if user_input is not None:
            # Validate user input
            if await is_valid(user_input):
                # Create and register Google OAuth2 Implementation
                self.flow_impl = GoogleLocalOAuth2Implementation(
                    self.hass,
                    DOMAIN,
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    OAUTH2_AUTHORIZE,
                    OAUTH2_TOKEN,
                )
                GoogleOAuth2ConfigFlow.async_register_implementation(
                    self.hass, self.flow_impl
                )

                # Choose the API
                return await self.async_step_api()

            errors["base"] = "auth_error"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID, default=CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET, default=CLIENT_SECRET): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_api(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get tokens for each of the selected APIs."""
        errors = {}
        if user_input is not None:
            self.flow_impl.scopes = []
            names = []
            for api, name in GOOGLE_APIS.items():
                if user_input.get(api):
                    self.flow_impl.scopes = self.flow_impl.scopes + SCOPES.get(api)
                    names.append(name)

            if self.flow_impl.scopes:
                self.flow_impl._name = ", ".join(names)
                return await self.async_step_pick_implementation()

            errors["base"] = "api_required"

        schema = {}
        for api in GOOGLE_APIS:
            schema[vol.Optional(api, default=False)] = bool
        return self.async_show_form(
            step_id="api", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow"""
        unique_id = hash(self.flow_impl.client_id + ", ".join(self.flow_impl.scopes))
        await self.async_set_unique_id(unique_id=unique_id)

        data[CONF_CLIENT_ID] = self.flow_impl.client_id
        data[CONF_CLIENT_SECRET] = self.flow_impl.client_secret

        return self.async_create_entry(title=self.flow_impl.name, data=data)
