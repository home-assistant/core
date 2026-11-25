"""LLM tools for the blueprint integration."""

from typing import override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN
from .models import Blueprint, DomainBlueprints

_NON_EMPTY_STRING = probatio.All(str, probatio.Strip, probatio.NonEmpty())
_METADATA_KEYS = ("description", "author", "source_url")


def _domain_blueprints(hass: HomeAssistant) -> dict[str, DomainBlueprints]:
    """Return the blueprints of each domain, like automation and script."""
    domain_blueprints: dict[str, DomainBlueprints] = hass.data.get(DOMAIN, {})
    return domain_blueprints


class ListBlueprintsTool(Tool):
    """LLM Tool to list the blueprints."""

    name = "blueprint__list_blueprints"
    title = "List blueprints"
    description = (
        "List the blueprints, sorted by domain and name, with their path, "
        "description, author and source URL. A blueprint that failed to load has "
        "an error instead. Use the domain and path with blueprint__get_blueprint "
        "to see its inputs."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "domain",
                description="Return only the blueprints of this domain, like "
                "automation or script.",
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the blueprints."""
        wanted_domain: str | None = self.parameters(tool_input.tool_args).get("domain")

        blueprints: list[JsonObjectType] = []
        # Copied, as a domain can register while blueprints load
        for domain, domain_blueprints in list(_domain_blueprints(hass).items()):
            if wanted_domain is not None and domain != wanted_domain:
                continue
            for path, value in (await domain_blueprints.async_get_blueprints()).items():
                item: JsonObjectType = {"domain": domain, "path": path}
                if isinstance(value, Blueprint):
                    item["name"] = value.name
                    for key in _METADATA_KEYS:
                        if metadata_value := value.metadata.get(key):
                            item[key] = metadata_value
                else:
                    item["error"] = str(value)
                blueprints.append(item)

        blueprints.sort(
            key=lambda item: (
                str(item["domain"]),
                str(item.get("name", "")).casefold(),
                str(item["path"]),
            )
        )
        return ToolResult(data={"blueprints": list[JsonValueType](blueprints)})


class GetBlueprintTool(Tool):
    """LLM Tool to get a blueprint."""

    name = "blueprint__get_blueprint"
    title = "Get blueprint"
    description = (
        "Get a blueprint as YAML: its inputs with their selectors and defaults, "
        "and the triggers, conditions and actions that use them. Use "
        "blueprint__list_blueprints to find the domain and path."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "domain", description="The domain, like automation or script."
            ): _NON_EMPTY_STRING,
            # Not stripped, as the path must match a listed file exactly
            probatio.Required(
                "path", description="The path of the blueprint."
            ): probatio.All(str, probatio.NonEmpty()),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the blueprint."""
        args = self.parameters(tool_input.tool_args)
        domain: str = args["domain"]
        path: str = args["path"]
        if (domain_blueprints := _domain_blueprints(hass).get(domain)) is None:
            raise HomeAssistantError(f"Blueprint '{domain}/{path}' not found.")

        # Only paths found in the blueprint folder, so a path cannot leave it
        value = (await domain_blueprints.async_get_blueprints()).get(path)
        if value is None:
            raise HomeAssistantError(f"Blueprint '{domain}/{path}' not found.")
        if not isinstance(value, Blueprint):
            raise HomeAssistantError(
                f"Blueprint '{domain}/{path}' failed to load: {value}"
            )
        return ToolResult(data={"domain": domain, "path": path, "yaml": value.yaml()})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the blueprint LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[ListBlueprintsTool(), GetBlueprintTool()])
