"""Helpers for the data entry flow."""
from __future__ import annotations

from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import HTTP_BAD_REQUEST, HTTP_NOT_FOUND
import homeassistant.helpers.config_validation as cv


class _BaseFlowManagerView(HomeAssistantView):
    """Foundation for flow manager views."""

    def __init__(self, flow_mgr: data_entry_flow.FlowManager) -> None:
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr

    # pylint: disable=no-self-use
    def _prepare_result_json(
        self, result: data_entry_flow.FlowResultDict
    ) -> data_entry_flow.FlowResultDict:
        """Convert result to JSON."""
        if result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            data = result.copy()
            data.pop("result")
            data.pop("data")
            return data

        if result["type"] != data_entry_flow.RESULT_TYPE_FORM:
            return result

        import voluptuous_serialize  # pylint: disable=import-outside-toplevel

        data = result.copy()

        schema = data["data_schema"]
        if schema is None:
            data["data_schema"] = []
        else:
            data["data_schema"] = voluptuous_serialize.convert(
                schema, custom_serializer=cv.custom_serializer
            )

        return data


class FlowManagerIndexView(_BaseFlowManagerView):
    """View to create config flows."""

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("handler"): vol.Any(str, list),
                vol.Optional("show_advanced_options", default=False): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle a POST request."""
        if isinstance(data["handler"], list):
            handler = tuple(data["handler"])
        else:
            handler = data["handler"]

        try:
            result = await self._flow_mgr.async_init(
                handler,  # type: ignore
                context={
                    "source": config_entries.SOURCE_USER,
                    "show_advanced_options": data["show_advanced_options"],
                },
            )
        except data_entry_flow.UnknownHandler:
            return self.json_message("Invalid handler specified", HTTP_NOT_FOUND)
        except data_entry_flow.UnknownStep:
            return self.json_message("Handler does not support user", HTTP_BAD_REQUEST)

        result = self._prepare_result_json(result)

        return self.json(result)


class FlowManagerResourceView(_BaseFlowManagerView):
    """View to interact with the flow manager."""

    async def get(self, request: web.Request, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        try:
            result = await self._flow_mgr.async_configure(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)

        result = self._prepare_result_json(result)

        return self.json(result)

    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    async def post(
        self, request: web.Request, flow_id: str, data: dict[str, Any]
    ) -> web.Response:
        """Handle a POST request."""
        try:
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)
        except vol.Invalid:
            return self.json_message("User input malformed", HTTP_BAD_REQUEST)

        result = self._prepare_result_json(result)

        return self.json(result)

    async def delete(self, request: web.Request, flow_id: str) -> web.Response:
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)

        return self.json_message("Flow aborted")
