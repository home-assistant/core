"""Helpers for the data entry flow."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Generic

from aiohttp import web
from typing_extensions import TypeVar
import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator

from . import config_validation as cv

_FlowManagerT = TypeVar(
    "_FlowManagerT",
    bound=data_entry_flow.FlowManager[Any, Any],
    default=data_entry_flow.FlowManager,
)


class _BaseFlowManagerView(HomeAssistantView, Generic[_FlowManagerT]):
    """Foundation for flow manager views."""

    def __init__(self, flow_mgr: _FlowManagerT) -> None:
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr

    def _prepare_result_json(
        self, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Convert result to JSON."""
        if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
            data = result.copy()
            data.pop("result")
            data.pop("data")
            data.pop("context")
            return data

        if "data_schema" not in result:
            return result

        data = result.copy()

        if (schema := data["data_schema"]) is None:
            data["data_schema"] = []  # type: ignore[typeddict-item]  # json result type
        else:
            data["data_schema"] = voluptuous_serialize.convert(
                schema, custom_serializer=cv.custom_serializer
            )

        return data


class FlowManagerIndexView(_BaseFlowManagerView[_FlowManagerT]):
    """View to create config flows."""

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("handler"): str,
                vol.Optional("show_advanced_options", default=False): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Initialize a POST request.

        Override `_post_impl` in subclasses which need
        to implement their own `RequestDataValidator`
        """
        return await self._post_impl(request, data)

    async def _post_impl(
        self, request: web.Request, data: dict[str, Any]
    ) -> web.Response:
        """Handle a POST request."""
        try:
            result = await self._flow_mgr.async_init(
                data["handler"],
                context=self.get_context(data),
            )
        except data_entry_flow.UnknownHandler:
            return self.json_message("Invalid handler specified", HTTPStatus.NOT_FOUND)
        except data_entry_flow.UnknownStep as err:
            return self.json_message(str(err), HTTPStatus.BAD_REQUEST)

        result = self._prepare_result_json(result)

        return self.json(result)

    def get_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return context."""
        return {"show_advanced_options": data["show_advanced_options"]}


class FlowManagerResourceView(_BaseFlowManagerView[_FlowManagerT]):
    """View to interact with the flow manager."""

    async def get(self, request: web.Request, /, flow_id: str) -> web.Response:
        """Get the current state of a data_entry_flow."""
        try:
            result = await self._flow_mgr.async_configure(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)

        result = self._prepare_result_json(result)

        return self.json(result)

    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    async def post(
        self, request: web.Request, data: dict[str, Any], flow_id: str
    ) -> web.Response:
        """Handle a POST request."""
        try:
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)
        except data_entry_flow.InvalidData as ex:
            return self.json({"errors": ex.schema_errors}, HTTPStatus.BAD_REQUEST)

        result = self._prepare_result_json(result)

        return self.json(result)

    async def delete(self, request: web.Request, flow_id: str) -> web.Response:
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)

        return self.json_message("Flow aborted")
