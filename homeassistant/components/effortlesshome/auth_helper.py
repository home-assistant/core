"""Authentication helper for handling Firebase token refresh across all API calls."""

import logging
from typing import Any, Callable, Coroutine, TypeVar, Awaitable
from functools import wraps

from oasira import OasiraAPIClient, OasiraAPIError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def _is_firebase_token_error(err: Exception) -> bool:
    """Check if the error is related to Firebase token expiration or invalidation."""
    msg = str(err).lower()
    status = getattr(err, "status", None) or getattr(err, "status_code", None)

    # Check for HTTP 401 status
    if status == 401:
        return True

    # Check for explicit Firebase token errors
    if "firebase token" in msg and ("expired" in msg or "invalid" in msg):
        return True

    # Check for generic 401 with token mention
    if "status 401" in msg and "token" in msg:
        return True

    # Check for common Firebase auth error patterns
    if any(
        pattern in msg
        for pattern in [
            "unauthorized",
            "invalid authentication",
            "token has expired",
            "invalid token",
            "authentication failed",
        ]
    ):
        return True

    return False


async def _refresh_id_token(hass) -> bool:
    """Refresh the Firebase ID token."""
    refresh_token = hass.data.get(DOMAIN, {}).get("refresh_token")
    if not refresh_token:
        _LOGGER.warning("No refresh token available - cannot refresh Firebase token")
        return False

    try:
        async with OasiraAPIClient() as api_client:
            result = await api_client.firebase_refresh_token(refresh_token)

        new_id_token = result.get("idToken")
        new_refresh_token = result.get("refreshToken") or refresh_token

        if not new_id_token:
            _LOGGER.error("Failed to refresh Firebase token - no idToken in response")
            return False

        hass.data[DOMAIN]["id_token"] = new_id_token
        hass.data[DOMAIN]["refresh_token"] = new_refresh_token

        entry = hass.data[DOMAIN].get("config_entry")
        if entry is not None:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    "id_token": new_id_token,
                    "refresh_token": new_refresh_token,
                },
            )

        _LOGGER.info("✅ Firebase ID token refreshed successfully")
        return True

    except OasiraAPIError as e:
        _LOGGER.error("Failed to refresh Firebase token: %s", e)
        return False
    except Exception as e:
        _LOGGER.exception("Unexpected error refreshing Firebase token: %s", e)
        return False


def with_token_refresh(
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """
    Decorator to automatically handle Firebase token refresh for API calls.

    This decorator wraps async functions that make API calls and automatically
    retries them with a refreshed token if a 401 authentication error occurs.

    Usage:
        @with_token_refresh
        async def my_api_call(hass, system_id, id_token):
            async with OasiraAPIClient(system_id=system_id, id_token=id_token) as client:
                return await client.some_method()
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        hass = None

        # Try to extract hass from args (usually first argument)
        if args and hasattr(args[0], "data"):
            hass = args[0]

        # If not found in args, try to get from kwargs
        if not hass and "hass" in kwargs:
            hass = kwargs["hass"]

        # If still not found, try to get from global HASSComponent
        if not hass:
            try:
                from . import HASSComponent

                hass = HASSComponent.get_hass()
            except ImportError:
                pass

        try:
            # First attempt
            return await func(*args, **kwargs)
        except OasiraAPIError as e:
            if hass and _is_firebase_token_error(e):
                _LOGGER.warning(
                    "Firebase token error detected, attempting refresh: %s", e
                )

                # Try to refresh token
                if await _refresh_id_token(hass):
                    _LOGGER.info("Token refreshed, retrying API call...")
                    try:
                        # Retry the function with refreshed token
                        return await func(*args, **kwargs)
                    except OasiraAPIError as retry_error:
                        _LOGGER.error(
                            "API call failed even after token refresh: %s", retry_error
                        )
                        raise retry_error
                else:
                    _LOGGER.error("Failed to refresh token, cannot retry API call")
                    raise e
            else:
                # Re-raise non-authentication errors
                raise e

    return wrapper


async def safe_api_call(
    hass, api_call_func: Callable[..., Awaitable[T]], *args, **kwargs
) -> T:
    """
    Execute an API call with automatic token refresh handling.

    This is an alternative to the decorator for cases where you need
    more control over the API call execution.

    Args:
        hass: HomeAssistant instance
        api_call_func: The async function to call
        *args, **kwargs: Arguments to pass to the API call function

    Returns:
        The result of the API call

    Raises:
        OasiraAPIError: If the API call fails even after token refresh
    """
    try:
        # First attempt
        return await api_call_func(*args, **kwargs)
    except OasiraAPIError as e:
        if _is_firebase_token_error(e):
            _LOGGER.warning("Firebase token error detected, attempting refresh: %s", e)

            # Try to refresh token
            if await _refresh_id_token(hass):
                _LOGGER.info("Token refreshed, retrying API call...")
                try:
                    # Retry the API call with refreshed token
                    return await api_call_func(*args, **kwargs)
                except OasiraAPIError as retry_error:
                    _LOGGER.error(
                        "API call failed even after token refresh: %s", retry_error
                    )
                    raise retry_error
            else:
                _LOGGER.error("Failed to refresh token, cannot retry API call")
                raise e
        else:
            # Re-raise non-authentication errors
            raise e
