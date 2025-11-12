"""The Amazon Alexa integration.

This integration provides OAuth2-based connection to Amazon Alexa using
Home Assistant's built-in OAuth2 framework with custom PKCE implementation.

Features:
    - OAuth2 with PKCE (RFC 7636) for secure authentication
    - Automatic token refresh via framework
    - Multi-account support via unique Amazon user_id
    - Encrypted token storage
    - Automatic reauth flow on token expiry

Architecture:
    - config_flow.py: User setup flow using AbstractOAuth2FlowHandler
    - oauth.py: Custom AlexaOAuth2Implementation with PKCE support
    - __init__.py (this file): Entry setup and OAuth registration

Setup Flow:
    1. User initiates integration (Settings → Add Integration → Alexa)
    2. Config flow redirects to Amazon OAuth with PKCE
    3. User authorizes on Amazon's site
    4. Amazon redirects back with authorization code
    5. Framework exchanges code for tokens (using PKCE verifier)
    6. Config flow fetches user profile and creates ConfigEntry
    7. async_setup_entry registers OAuth implementation
    8. Framework handles token storage and refresh automatically

Token Lifecycle:
    - Tokens stored in Home Assistant's encrypted storage
    - Framework automatically refreshes before expiry
    - Reauth flow triggered if refresh fails
    - User notified via persistent notification

Example Config Entry Data:
    {
        "auth_implementation": "alexa",
        "token": {
            "access_token": "Atza|...",
            "refresh_token": "Atzr|...",
            "expires_in": 3600,
            "token_type": "Bearer",
            "expires_at": 1699123456.789
        },
        "user_id": "amzn1.account.XXX",
        "name": "John Doe",
        "email": "john@example.com"
    }
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN
from .oauth import AlexaOAuth2Implementation

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
# Phase 1: No platforms yet (future: notify, etc.)
PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Amazon Alexa component.

    This is called when Home Assistant starts. Since Alexa is an OAuth
    integration, it should only be configured via the UI (config flow),
    not via YAML.

    Args:
        hass: Home Assistant instance
        config: YAML configuration (deprecated for OAuth integrations)

    Returns:
        True (setup always succeeds - actual setup happens in async_setup_entry)

    Notes:
        - YAML configuration is not supported for OAuth integrations
        - Users must use the UI to add Alexa integration
        - This function just initializes hass.data storage
    """
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        _LOGGER.warning(
            "YAML configuration for Alexa is not supported. "
            "Please remove it from configuration.yaml and use "
            "Settings → Integrations → Add Integration → Alexa"
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Amazon Alexa from a config entry.

    This is the main entry point for the integration. It:
    1. Registers our custom OAuth implementation (if not already registered)
    2. Creates OAuth session for API calls
    3. Stores session in hass.data for platforms to use
    4. Forwards entry setup to platforms (if any)

    The OAuth implementation MUST be registered before the framework can
    use it for token management. We register it here (after user provides
    credentials via config flow) rather than in async_setup because we need
    the client_id and client_secret from the config entry.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry created by config flow containing:
            - auth_implementation: Domain name ("alexa")
            - token: OAuth tokens (access, refresh)
            - user_id: Amazon user ID
            - name: User's name (optional)
            - email: User's email (optional)

    Returns:
        True if setup successful

    Raises:
        ConfigEntryAuthFailed: Authentication failed (triggers reauth)
        ConfigEntryNotReady: Temporary failure (will retry)

    Flow:
        1. Extract client credentials from framework's token data
        2. Register our AlexaOAuth2Implementation with PKCE support
        3. Get implementation for this entry from framework
        4. Create OAuth2Session for API calls
        5. Store session in hass.data for platforms
        6. Forward setup to platforms

    Notes:
        - OAuth implementation is registered per-domain, not per-entry
        - Multiple entries (accounts) share the same implementation
        - Framework handles token storage, refresh, and reauth triggers
        - Session provides async_get_access_token() for API calls
    """
    _LOGGER.info(
        "Setting up Alexa integration for user %s (entry_id=%s)",
        entry.data.get("name", "Unknown"),
        entry.entry_id,
    )

    # Initialize integration storage if not exists
    hass.data.setdefault(DOMAIN, {})

    # Get existing implementations for this domain
    current_implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )

    # Register OAuth implementation if not already registered
    # Note: Implementation is registered per-domain, not per-entry
    # Multiple accounts (entries) share the same implementation
    if DOMAIN not in current_implementations:
        _LOGGER.debug("Registering AlexaOAuth2Implementation with PKCE support")

        # Extract client credentials from config entry
        # These were stored during the initial OAuth config flow
        client_id = entry.data.get("client_id")
        client_secret = entry.data.get("client_secret")

        if not client_id or not client_secret:
            _LOGGER.error(
                "Missing client_id or client_secret in config entry. "
                "Please remove and re-add the integration."
            )
            return False

        # Register OAuth implementation with stored credentials
        config_entry_oauth2_flow.async_register_implementation(
            hass,
            DOMAIN,
            AlexaOAuth2Implementation(
                hass,
                DOMAIN,
                client_id,
                client_secret,
            ),
        )
        _LOGGER.info(
            "Registered AlexaOAuth2Implementation with PKCE support for entry %s",
            entry.entry_id
        )

    # Get implementation for this entry
    try:
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    except ValueError as err:
        _LOGGER.error(
            "Failed to get OAuth implementation for entry %s: %s",
            entry.entry_id,
            err
        )
        return False

    # Create OAuth2 session for this entry
    # This provides async_get_access_token() for making API calls
    # The framework automatically refreshes tokens as needed
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Test token validity by attempting to get access token
    # This will trigger a refresh if the token is expired
    try:
        await session.async_ensure_token_valid()
        _LOGGER.debug(
            "OAuth token validated for entry %s (user=%s)",
            entry.entry_id,
            entry.data.get("name", "Unknown"),
        )
    except Exception as err:
        _LOGGER.error(
            "Failed to validate OAuth token for entry %s: %s",
            entry.entry_id,
            err
        )
        # Don't fail setup - framework will trigger reauth if needed
        # return False

    # Store OAuth session in hass.data for platforms to use
    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "implementation": implementation,
        "user_id": entry.data.get("user_id"),
        "name": entry.data.get("name"),
        "email": entry.data.get("email"),
    }

    # Forward entry setup to platforms (if any defined)
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Amazon Alexa integration configured for user %s (user_id=%s)",
        entry.data.get("name", "Unknown"),
        entry.data.get("user_id", "Unknown")[:8],  # Log partial ID for privacy
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Amazon Alexa config entry.

    This is called when the integration is being removed or disabled.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry being removed

    Returns:
        True if unload successful

    Flow:
        1. Unload platforms (if any)
        2. Clean up entry data from hass.data
        3. Framework automatically handles token cleanup

    Notes:
        - Framework automatically stops token refresh task
        - Tokens remain in storage (for potential re-add)
        - To fully remove tokens, user must delete integration
    """
    _LOGGER.info(
        "Unloading Alexa integration for user %s (entry_id=%s)",
        entry.data.get("name", "Unknown"),
        entry.entry_id,
    )

    # Unload platforms
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if not unload_ok:
            _LOGGER.warning(
                "Failed to unload platforms for entry %s",
                entry.entry_id
            )
            return False

    # Clean up stored data
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Cleaned up data for entry %s", entry.entry_id)

    _LOGGER.info(
        "Alexa integration unload complete for entry %s",
        entry.entry_id
    )

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new format.

    This handles version upgrades for ConfigEntry data schema.

    Args:
        hass: Home Assistant instance
        entry: ConfigEntry to migrate

    Returns:
        True if migration successful, False otherwise

    Example:
        Version 1 → Version 2:
        - Add new required fields
        - Transform data format
        - Update entry.version

    Notes:
        - Migration is called automatically by Home Assistant
        - Should be idempotent (safe to run multiple times)
        - Return False to prevent loading if migration fails
    """
    _LOGGER.info(
        "Checking Alexa config entry migration (current version=%s)",
        entry.version
    )

    # Phase 1: No migrations needed (version 1 is current)
    if entry.version == 1:
        _LOGGER.debug("Config entry already at version 1, no migration needed")
        return True

    # Future migrations would go here
    # Example:
    # if entry.version == 1:
    #     # Migrate v1 → v2
    #     new_data = {**entry.data}
    #     new_data["new_field"] = "default_value"
    #     hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    #     _LOGGER.info("Migrated config entry to version 2")
    #     return True

    _LOGGER.error(
        "Unknown config entry version %s, cannot migrate",
        entry.version
    )
    return False
