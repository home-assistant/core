"""Config flow for the Model Context Protocol Server integration."""

import logging
import secrets
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.util import slugify

from .const import CONF_URL_ID, DOMAIN
from .http import STREAMABLE_API_BASE

_LOGGER = logging.getLogger(__name__)

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"

# Above this many selected APIs a generic name and random URL identifier is used
MAX_NAMED_APIS = 2
# Number of random bytes used for the URL identifier (2 hex characters each)
URL_ID_BYTES = 3
# Generic name used when more than MAX_NAMED_APIS APIs are exposed
GENERIC_NAME = "MCP Server"


class ModelContextServerProtocolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol Server."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._llm_api_ids: list[str] = []
        self._title: str = ""
        self._url_id: str = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                self._llm_api_ids = user_input[CONF_LLM_HASS_API]
                self._title, self._url_id = self._async_generate_name(self._llm_api_ids)
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_schema(),
            description_placeholders={"more_info_url": MORE_INFO_URL},
            errors=errors,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm creation and show the URLs serving the new config entry."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_LLM_HASS_API: self._llm_api_ids,
                    CONF_URL_ID: self._url_id,
                },
            )

        path = f"{STREAMABLE_API_BASE}/{self._url_id}"
        return self.async_show_form(
            step_id="finish",
            description_placeholders={
                "name": self._title,
                "internal_url": self._async_url(path, external=False),
                "external_url": self._async_url(path, external=True),
            },
        )

    def _async_generate_name(self, llm_api_ids: list[str]) -> tuple[str, str]:
        """Return a title and a unique URL identifier for the selected APIs."""
        if len(llm_api_ids) <= MAX_NAMED_APIS:
            llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
            title = ", ".join(llm_apis.get(api_id, api_id) for api_id in llm_api_ids)
            url_id = slugify("_".join(llm_api_ids))
        else:
            title = self._async_unique_title(GENERIC_NAME)
            url_id = secrets.token_hex(URL_ID_BYTES)
        return title, self._async_unique_url_id(url_id)

    def _async_unique_url_id(self, url_id: str) -> str:
        """Return a URL identifier that does not collide with existing entries."""
        existing = {
            entry.data.get(CONF_URL_ID) for entry in self._async_current_entries()
        }
        if url_id not in existing:
            return url_id
        suffix = 2
        while (candidate := f"{url_id}_{suffix}") in existing:
            suffix += 1
        return candidate

    def _async_unique_title(self, title: str) -> str:
        """Return a title that does not collide with existing entries."""
        existing = {entry.title for entry in self._async_current_entries()}
        if title not in existing:
            return title
        suffix = 2
        while (candidate := f"{title} {suffix}") in existing:
            suffix += 1
        return candidate

    def _async_schema(self, default: list[str] | None = None) -> vol.Schema:
        """Return the schema for selecting the LLM APIs to expose."""
        if not default:
            default = [llm.LLM_API_ASSIST]
        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
        return vol.Schema(
            {
                vol.Optional(
                    CONF_LLM_HASS_API,
                    default=default,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                label=name,
                                value=llm_api_id,
                            )
                            for llm_api_id, name in llm_apis.items()
                        ],
                        multiple=True,
                    )
                ),
            }
        )

    def _async_url(self, path: str, *, external: bool) -> str:
        """Return the internal or external URL serving the given path."""
        try:
            base_url = get_url(
                self.hass,
                allow_internal=not external,
                allow_external=external,
            )
        except NoURLAvailableError:
            return "-"
        return f"{base_url}{path}"
