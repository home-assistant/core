"""Rest API for Home Assistant."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "llm_tools"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the LLM Tools API with the HTTP interface."""
    hass.http.register_view(LLMToolsApiView)
    hass.http.register_view(LLMToolsListView)
    hass.http.register_view(LLMToolView)

    return True


class LLMToolsApiView(HomeAssistantView):
    """View to get LLM APIs."""

    url = "/api/llm_tools"
    name = "api:llm_tools"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get LLM Tools list."""
        hass = request.app[KEY_HASS]
        return self.json([api.name for api in llm.async_get_apis(hass)])


class LLMToolsListView(HomeAssistantView):
    """View to get LLM Tools list."""

    url = "/api/llm_tools/{api_name}"
    name = "api:llm_tools:api"

    @ha.callback
    def get(self, request: web.Request, api_name: str) -> web.Response:
        """Get LLM Tools list."""
        hass = request.app[KEY_HASS]
        for api in llm.async_get_apis(hass):
            if api.name == api_name:
                break
        else:
            return self.json_message("API not found", HTTPStatus.NOT_FOUND)

        return self.json(async_llm_tools_json(api))

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("tool_name"): cv.string,
                vol.Optional("tool_args", default={}): {cv.string: object},
                vol.Optional("user_input"): cv.string,
                vol.Optional("language"): cv.string,
                vol.Optional("device_id"): cv.string,
            }
        )
    )
    async def post(
        self, request: web.Request, data: dict[str, Any], api_name: str
    ) -> web.Response:
        """Call an LLM Tool."""
        hass = request.app[KEY_HASS]
        for api in llm.async_get_apis(hass):
            if api.name == api_name:
                break
        else:
            return self.json_message("API not found", HTTPStatus.NOT_FOUND)

        tool_name = data["tool_name"]

        if not tool_name:
            return self.json_message("tool_name not provided", HTTPStatus.BAD_REQUEST)

        _LOGGER.info("Tool call: %s(%s)", tool_name, data["tool_args"])

        try:
            tool_input = llm.ToolInput(
                tool_name=tool_name,
                tool_args=data["tool_args"],
                platform=DOMAIN,
                context=self.context(request),
                user_prompt=data.get("user_input"),
                language=data.get("language", hass.config.language),
                assistant=CONVERSATION_DOMAIN,
                device_id=data.get("device_id"),
            )
            function_response = await api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as e:
            function_response = {"error": type(e).__name__}
            if str(e):
                function_response["error_text"] = str(e)
            _LOGGER.info("Tool response: %s", function_response)
            return self.json(function_response, HTTPStatus.INTERNAL_SERVER_ERROR)

        _LOGGER.info("Tool response: %s", function_response)

        return self.json(function_response)


class LLMToolView(HomeAssistantView):
    """View to get LLM Tool."""

    url = "/api/llm_tools/{api_name}/{tool_name}"
    name = "api:llm_tools:api:tool"

    @ha.callback
    def get(self, request: web.Request, api_name: str, tool_name: str) -> web.Response:
        """Get LLM Tool specs."""
        hass = request.app[KEY_HASS]
        for api in llm.async_get_apis(hass):
            if api.name == api_name:
                break
        else:
            return self.json_message("API not found", HTTPStatus.NOT_FOUND)

        for tool in async_llm_tools_json(api):
            if tool["name"] == tool_name:
                break
        else:
            return self.json_message("Tool not found", HTTPStatus.NOT_FOUND)
        return self.json(tool)

    @RequestDataValidator(vol.Maybe(vol.Schema({cv.string: object})))
    async def post(
        self,
        request: web.Request,
        data: dict[str, Any] | None,
        api_name: str,
        tool_name: str,
    ) -> web.Response:
        """Call an the LLM Tool."""
        hass = request.app[KEY_HASS]
        for api in llm.async_get_apis(hass):
            if api.name == api_name:
                break
        else:
            return self.json_message("API not found", HTTPStatus.NOT_FOUND)

        for tool in api.async_get_tools():
            if tool.name == tool_name:
                break
        else:
            return self.json_message("Tool not found", HTTPStatus.NOT_FOUND)

        _LOGGER.info("Tool call: %s(%s)", tool_name, data)

        try:
            tool_input = llm.ToolInput(
                tool_name=tool_name,
                tool_args=data or {},
                platform=DOMAIN,
                context=self.context(request),
                user_prompt=None,
                language=hass.config.language,
                assistant=CONVERSATION_DOMAIN,
                device_id=None,
            )
            function_response = await api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as e:
            function_response = {"error": type(e).__name__}
            if str(e):
                function_response["error_text"] = str(e)
            _LOGGER.info("Tool response: %s", function_response)
            return self.json(function_response, HTTPStatus.INTERNAL_SERVER_ERROR)

        _LOGGER.info("Tool response: %s", function_response)

        return self.json(function_response)


@ha.callback
def async_llm_tools_json(api: llm.API) -> list[dict[str, Any]]:
    """Generate LLM Tools data to JSONify."""

    def format_tool(tool: llm.Tool) -> dict[str, Any]:
        """Format tool specification."""
        tool_spec = {"name": tool.name}
        if tool.description:
            tool_spec["description"] = tool.description
        tool_spec["parameters"] = convert(tool.parameters)
        return tool_spec

    return [format_tool(tool) for tool in api.async_get_tools()]
