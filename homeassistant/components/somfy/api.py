"""API for Somfy bound to HASS OAuth."""
from asyncio import run_coroutine_threadsafe
from functools import partial

import requests
from pymfy.api import somfy_api

from homeassistant import core, config_entries
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntrySomfyApi(somfy_api.AbstractSomfyApi):
    """Provide a Somfy API tied into an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize the Config Entry Somfy API."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )

    def get(self, path):
        """Fetch a URL from the Somfy API."""
        return run_coroutine_threadsafe(
            self._request("get", path), self.hass.loop
        ).result()

    def post(self, path, *, json):
        """Post data to the Somfy API."""
        return run_coroutine_threadsafe(
            self._request("post", path, json=json), self.hass.loop
        ).result()

    async def _request(self, method, path, **kwargs):
        """Make a request."""
        await self.session.async_ensure_token_valid()

        return await self.hass.async_add_executor_job(
            partial(
                requests.request,
                method,
                f"{self.base_url}{path}",
                **kwargs,
                headers={
                    **kwargs.get("headers", {}),
                    "authorization": f"Bearer {self.config_entry.data['token']['access_token']}",
                },
            )
        )
