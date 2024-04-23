"""Decorator for view methods to help with data validation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from http import HTTPStatus
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from aiohttp import web
import voluptuous as vol

from .view import HomeAssistantView

_HassViewT = TypeVar("_HassViewT", bound=HomeAssistantView)
_P = ParamSpec("_P")

_LOGGER = logging.getLogger(__name__)


class RequestDataValidator:
    """Decorator that will validate the incoming data.

    Takes in a voluptuous schema and adds 'data' as
    keyword argument to the function call.

    Will return a 400 if no JSON provided or doesn't match schema.
    """

    def __init__(self, schema: vol.Schema, allow_empty: bool = False) -> None:
        """Initialize the decorator."""
        if isinstance(schema, dict):
            schema = vol.Schema(schema)

        self._schema = schema
        self._allow_empty = allow_empty

    def __call__(
        self,
        method: Callable[
            Concatenate[_HassViewT, web.Request, dict[str, Any], _P],
            Awaitable[web.Response],
        ],
    ) -> Callable[
        Concatenate[_HassViewT, web.Request, _P],
        Coroutine[Any, Any, web.Response],
    ]:
        """Decorate a function."""

        @wraps(method)
        async def wrapper(
            view: _HassViewT, request: web.Request, *args: _P.args, **kwargs: _P.kwargs
        ) -> web.Response:
            """Wrap a request handler with data validation."""
            raw_data = None
            try:
                raw_data = await request.json()
            except ValueError:
                if not self._allow_empty or (await request.content.read()) != b"":
                    _LOGGER.error("Invalid JSON received")
                    return view.json_message("Invalid JSON.", HTTPStatus.BAD_REQUEST)
                raw_data = {}

            try:
                data: dict[str, Any] = self._schema(raw_data)
            except vol.Invalid as err:
                _LOGGER.error("Data does not match schema: %s", err)
                return view.json_message(
                    f"Message format incorrect: {err}", HTTPStatus.BAD_REQUEST
                )

            return await method(view, request, data, *args, **kwargs)

        return wrapper
