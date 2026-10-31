"""Utilities for the Seafile integration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aioseafile import (
    SeafileAuthenticationError,
    SeafileError,
    SeafilePermissionError,
    SeafileTimeoutError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER


@asynccontextmanager
async def handle_seafile_errors() -> AsyncGenerator[None]:
    """Raise translated errors for failed Seafile API calls."""
    try:
        yield
    except SeafileAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except SeafilePermissionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="permission_denied",
        ) from err
    except SeafileTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err
    except SeafileError as err:
        LOGGER.debug("Seafile API call failed: %s", err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_error",
        ) from err
