"""Config flow for the Model Context Protocol Server integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm, selector
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.util import slugify

from .const import CONF_URL_ID, DOMAIN
from .http import STREAMABLE_API_BASE, async_get_mcp_server_path
from .types import MCPServerConfigEntry

_LOGGER = logging.getLogger(__name__)

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"

# Number of selected APIs above which an AI Task is used to propose a name
AI_TASK_NAME_THRESHOLD = 2


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
                self._title, self._url_id = await self._async_generate_name(
                    self._llm_api_ids
                )
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing config entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._async_schema(entry.data.get(CONF_LLM_HASS_API)),
            description_placeholders=self._async_url_placeholders(entry),
            errors=errors,
        )

    async def _async_generate_name(self, llm_api_ids: list[str]) -> tuple[str, str]:
        """Return a title and a unique URL identifier for the selected APIs."""
        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
        title = ", ".join(llm_apis.get(api_id, api_id) for api_id in llm_api_ids)
        url_id = slugify("_".join(llm_api_ids))

        if len(llm_api_ids) > AI_TASK_NAME_THRESHOLD:
            names = [llm_apis.get(api_id, api_id) for api_id in llm_api_ids]
            if proposal := await self._async_ai_task_name(names):
                title, url_id = proposal

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

    async def _async_ai_task_name(self, names: list[str]) -> tuple[str, str] | None:
        """Use an AI Task to propose a title and slug, or None if unavailable."""
        if "ai_task" not in self.hass.config.components:
            return None
        try:
            result = await ai_task.async_generate_data(
                self.hass,
                task_name="MCP server name",
                instructions=(
                    "Suggest a short, friendly name and a matching short "
                    "URL-safe slug for a Model Context Protocol server that "
                    f"exposes these Home Assistant APIs: {', '.join(names)}."
                ),
                structure=vol.Schema(
                    {
                        vol.Required("title"): selector.selector({"text": {}}),
                        vol.Required("slug"): selector.selector({"text": {}}),
                    }
                ),
            )
        except HomeAssistantError as err:
            _LOGGER.debug("AI Task name suggestion unavailable: %s", err)
            return None

        if not isinstance(result.data, dict):
            return None
        title = str(result.data.get("title") or "").strip()
        slug = slugify(str(result.data.get("slug") or ""))
        if not title or not slug:
            return None
        return title, slug

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

    def _async_url_placeholders(self, entry: MCPServerConfigEntry) -> dict[str, str]:
        """Return description placeholders with the URLs serving the entry."""
        path = async_get_mcp_server_path(entry)
        return {
            "more_info_url": MORE_INFO_URL,
            "internal_url": self._async_url(path, external=False),
            "external_url": self._async_url(path, external=True),
        }

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
