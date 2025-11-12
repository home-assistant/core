"""Config flow for Amazon Alexa integration.

This module implements the Home Assistant config flow for setting up the
Amazon Alexa integration using the built-in OAuth2 framework with our
custom PKCE implementation.

Flow Types:
    - User flow: Initial setup via OAuth2
    - Reauth flow: Re-authenticate when tokens expire

Security Features:
    - OAuth2 Authorization Code flow with PKCE (RFC 7636)
    - State parameter for CSRF protection (managed by framework)
    - Unique ID based on Amazon user_id (prevents duplicate accounts)
    - Client credentials encrypted in ConfigEntry storage
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, REQUIRED_SCOPES
from .oauth import AlexaOAuth2Implementation

_LOGGER = logging.getLogger(__name__)


class AlexaFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle Amazon Alexa OAuth2 config flow.

    This flow handler uses Home Assistant's built-in OAuth2 framework with
    our custom AlexaOAuth2Implementation (defined in oauth.py) that provides
    PKCE support for Amazon Login with Amazon (LWA) security requirements.

    Flow Steps:
        1. User enters client_id and client_secret
        2. Framework redirects to Amazon OAuth with PKCE challenge
        3. User authorizes on Amazon's site
        4. Amazon redirects back with authorization code
        5. Framework exchanges code for tokens (with PKCE verifier)
        6. We fetch Amazon user profile for unique_id
        7. ConfigEntry created with tokens

    Security:
        - PKCE (Proof Key for Code Exchange) prevents authorization code interception
        - State parameter prevents CSRF attacks (framework handles this)
        - Unique ID based on Amazon user_id prevents duplicate accounts
        - Client credentials encrypted in config entry storage

    Example:
        >>> # User clicks Settings → Integrations → Add Integration → Alexa
        >>> # Flow shows form for client_id and client_secret
        >>> # User submits → redirect to Amazon OAuth
        >>> # User authorizes → redirect back to HA
        >>> # Flow creates ConfigEntry with encrypted tokens
    """

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger for this flow."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data to append to authorization URL.

        This provides the OAuth scope to request from Amazon.
        Scope 'profile:user_id' allows access to user's Amazon ID and profile.

        Returns:
            Dictionary with scope parameter for authorization URL

        Notes:
            - Scope must match Amazon LWA security profile configuration
            - Required scope defined in const.py: REQUIRED_SCOPES
            - Framework automatically includes this in authorization URL
        """
        return {"scope": REQUIRED_SCOPES}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user.

        This is the entry point for the config flow. We first collect client_id
        and client_secret from the user, then register our OAuth implementation,
        and finally proceed with the standard OAuth flow.

        This "hybrid" approach solves the chicken-and-egg problem where
        AbstractOAuth2FlowHandler needs an implementation to be registered,
        but we need credentials from the user to create the implementation.

        Args:
            user_input: Optional dict containing CONF_CLIENT_ID and CONF_CLIENT_SECRET

        Returns:
            FlowResult with either:
                - Form to collect credentials (if user_input is None)
                - Redirect to OAuth flow (after registering implementation)

        Flow:
            1. User initiates integration → show credential form
            2. User submits client_id and client_secret
            3. Register AlexaOAuth2Implementation with those credentials
            4. Proceed to OAuth flow via async_step_pick_implementation
            5. After OAuth completes, async_oauth_create_entry is called

        Notes:
            - Multiple Amazon accounts are supported (different user_ids)
            - Same account cannot be added twice (unique_id check in async_oauth_create_entry)
            - Implementation is registered per-domain (shared across all accounts)
        """
        errors = {}

        if user_input is not None:
            # User submitted credentials - register OAuth implementation
            client_id = user_input[CONF_CLIENT_ID]
            client_secret = user_input[CONF_CLIENT_SECRET]

            # Check if implementation already registered
            current_implementations = await config_entry_oauth2_flow.async_get_implementations(
                self.hass, DOMAIN
            )

            if DOMAIN not in current_implementations:
                # Register our OAuth implementation with PKCE
                _LOGGER.debug(
                    "Registering AlexaOAuth2Implementation (client_id=%s...)",
                    client_id[:10]
                )
                config_entry_oauth2_flow.async_register_implementation(
                    self.hass,
                    DOMAIN,
                    AlexaOAuth2Implementation(
                        self.hass,
                        DOMAIN,
                        client_id,
                        client_secret,
                    ),
                )

            # Get the implementation and set it as flow_impl
            implementations = await config_entry_oauth2_flow.async_get_implementations(
                self.hass, DOMAIN
            )
            self.flow_impl = implementations[DOMAIN]

            # Now proceed directly to auth step (bypassing pick_implementation)
            return await self.async_step_auth()

        # Show form to collect credentials
        data_schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "setup_url": "https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html"
            },
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for Amazon Alexa after OAuth completes.

        This is called by the framework after successful OAuth token exchange.
        We fetch the Amazon user profile to get a unique user_id for duplicate
        detection and account identification.

        Args:
            data: OAuth data from framework containing:
                - token: Access token data (access_token, refresh_token, expires_in)
                - auth_implementation: Implementation domain (DOMAIN)

        Returns:
            FlowResult with one of:
                - Created entry (success)
                - Abort (cannot connect, invalid auth, or duplicate account)

        Flow:
            1. Extract access_token from data
            2. Call Amazon profile API to get user_id
            3. Set unique_id to prevent duplicate accounts
            4. Create ConfigEntry with tokens and profile data

        Error Handling:
            - cannot_connect: Network error fetching profile
            - invalid_auth: Amazon returned error or missing user_id
            - already_configured: Same Amazon account already added (via unique_id)

        Example:
            >>> # After OAuth completes:
            >>> data = {
            ...     "token": {
            ...         "access_token": "Atza|...",
            ...         "refresh_token": "Atzr|...",
            ...         "expires_in": 3600,
            ...         "token_type": "Bearer"
            ...     },
            ...     "auth_implementation": "alexa"
            ... }
            >>> # Flow fetches profile, creates entry
        """
        session = async_get_clientsession(self.hass)
        token = data["token"]

        # Fetch Amazon user profile to get unique user_id
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
        }

        try:
            async with session.get(
                "https://api.amazon.com/user/profile",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error(
                        "Failed to fetch Amazon user profile (status=%d)", resp.status
                    )
                    return self.async_abort(reason="cannot_connect")

                profile = await resp.json()

        except ClientError as err:
            _LOGGER.error("Network error fetching Amazon user profile: %s", err)
            return self.async_abort(reason="cannot_connect")

        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Amazon user profile: %s", err)
            return self.async_abort(reason="invalid_auth")

        # Extract user_id for unique identification
        user_id = profile.get("user_id")
        if not user_id:
            _LOGGER.error("Amazon profile missing user_id: %s", profile)
            return self.async_abort(reason="invalid_auth")

        # Set unique_id to prevent duplicate accounts
        # This ensures the same Amazon account cannot be added twice
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()

        _LOGGER.info(
            "Creating Alexa integration entry for user %s (user_id=%s)",
            profile.get("name", "Unknown"),
            user_id[:8],  # Log partial ID for privacy
        )

        # Get client credentials from the registered implementation
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, DOMAIN
        )
        impl = implementations[DOMAIN]

        # Create config entry with OAuth tokens and profile data
        # Framework automatically saves tokens in encrypted storage
        # Save client credentials for re-registering implementation on restart
        return self.async_create_entry(
            title=f"Amazon Alexa ({profile.get('name', 'User')})",
            data={
                "auth_implementation": DOMAIN,
                "token": token,
                "user_id": user_id,
                "name": profile.get("name"),
                "email": profile.get("email"),
                "client_id": impl.client_id,
                "client_secret": impl.client_secret,
            },
        )
