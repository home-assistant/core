"""Config flow for the Osmund integration: a personal key from Min side."""

import logging
from typing import Any, override

from osmund import (
    API_ACCESS_OPEN,
    KEY_PREFIX,
    SCOPE_PRICES,
    OsmundAccessError,
    OsmundAuthError,
    OsmundClient,
    OsmundError,
    OsmundScopeError,
    OsmundUnavailableError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, KEY_URL

_LOGGER = logging.getLogger(__name__)

DOCS_URL = "https://osmundenergi.dk/docs/osmund-api/"

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class OsmundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Osmund."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the key, and check it against the API before saving it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            errors = await self._check(key)
            if not errors:
                return self.async_create_entry(title="Osmund", data={CONF_API_KEY: key})
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"key_url": KEY_URL, "docs_url": DOCS_URL},
        )

    async def _check(self, key: str) -> dict[str, str]:
        """The form's errors for a key: none when it can read the prices of a location."""
        if not key.startswith(KEY_PREFIX):
            return {CONF_API_KEY: "invalid_format"}
        client = OsmundClient(async_get_clientsession(self.hass), key)
        try:
            me = await client.me()
            locations = await client.locations()
        except OsmundError as err:
            return {"base": _form_error(err)}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        if SCOPE_PRICES not in me.scopes:
            return {"base": "missing_scope"}
        if not any(location.api_access == API_ACCESS_OPEN for location in locations):
            return {"base": "no_access"}
        return {}


def _form_error(err: OsmundError) -> str:
    """The form's error for an API error."""
    if isinstance(err, OsmundAuthError):
        return "invalid_auth"
    if isinstance(err, OsmundScopeError):
        return "missing_scope"
    if isinstance(err, OsmundAccessError):
        return "no_access"
    if isinstance(err, OsmundUnavailableError):
        return "unavailable"
    return "cannot_connect"
