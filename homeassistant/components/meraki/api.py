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
    # The library creates its own httpx client, which loads SSL certificates
    # when it is created. That blocks, and the library takes no client from us.
    return await hass.async_add_executor_job(
        partial(
            AsyncDashboardAPI,
            # The library falls back to an environment variable without a key.
            api_key=api_key,
            caller=CALLER,
            # Log through the "meraki" logger only, without the library's own
            # log file in the working directory or console output.
            inherit_logging_config=True,
            output_log=False,
            print_console=False,
            # Smart flow writes a cache to the home directory. It also cannot map
            # the networks of getOrganizationNetworks to their organization, so it
            # would not throttle the client requests.
            smart_flow_enabled=False,
            # The library defaults (60 s timeout, 5 attempts, 60 s waits on 429)
            # are too long for an update every minute.
            single_request_timeout=10,
            maximum_retries=2,
            nginx_429_retry_wait_time=5,
        )
    )


def is_auth_error(err: APIError) -> bool:
    """Return True if the API key is invalid or has no access."""
    return err.status in (401, 403)
