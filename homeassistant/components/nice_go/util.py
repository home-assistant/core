"""Utilities for Nice G.O."""

from functools import wraps

from aiohttp import ClientError
from nice_go import ApiError, AuthFailedError

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN


def retry(translation_key: str):
    """Retry decorator to handle API errors."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except (ApiError, ClientError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=translation_key,
                    translation_placeholders={"exception": str(err)},
                ) from err
            except AuthFailedError:
                # Try refreshing token and retry
                try:
                    await args[0].coordinator.update_refresh_token()
                    return await func(*args, **kwargs)
                except (ApiError, ClientError, UpdateFailed) as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key=translation_key,
                        translation_placeholders={"exception": str(err)},
                    ) from err
                except (AuthFailedError, ConfigEntryAuthFailed) as err:
                    args[0].coordinator.config_entry.async_start_reauth(args[0].hass)
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key=translation_key,
                        translation_placeholders={"exception": str(err)},
                    ) from err

        return wrapper

    return decorator
