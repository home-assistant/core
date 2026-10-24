"""Create clients for the Meraki Dashboard API."""

from functools import partial

from meraki import APIError
from meraki.aio import AsyncDashboardAPI

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

# Meraki asks API callers to identify as "<application>/<version> <vendor>".
CALLER = f"HomeAssistant/{HA_VERSION} HomeAssistant"


async def async_create_client(hass: HomeAssistant, api_key: str) -> AsyncDashboardAPI:
    """Create a Dashboard API client."""
    # The client loads SSL certificates when it is created, which blocks.
    return await hass.async_add_executor_job(
        partial(
            AsyncDashboardAPI,
            api_key=api_key,
            caller=CALLER,
            suppress_logging=True,
            # Smart flow persists a cache in the home directory.
            smart_flow_enabled=False,
        )
    )


def is_auth_error(err: APIError) -> bool:
    """Return True if the API key is invalid or has no access."""
    return err.status in (401, 403)
