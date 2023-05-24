"""Support for views."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
from aiohttp.typedefs import LooseHeaders
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPInternalServerError,
    HTTPUnauthorized,
)
from aiohttp.web_urldispatcher import AbstractRoute
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import Context, HomeAssistant, is_callback
from homeassistant.helpers.json import (
    find_paths_unserializable_data,
    json_bytes,
    json_dumps,
)
from homeassistant.util.json import JSON_ENCODE_EXCEPTIONS, format_unserializable_data

from .const import KEY_AUTHENTICATED

_LOGGER = logging.getLogger(__name__)


class HomeAssistantView:
    """Base view for all views."""

    url: str | None = None
    extra_urls: list[str] = []
    # Views inheriting from this class can override this
    requires_auth = True
    cors_allowed = False

    @staticmethod
    def context(request: web.Request) -> Context:
        """Generate a context from a request."""
        if (user := request.get("hass_user")) is None:
            return Context()

        return Context(user_id=user.id)

    @staticmethod
    def json(
        result: Any,
        status_code: HTTPStatus | int = HTTPStatus.OK,
        headers: LooseHeaders | None = None,
    ) -> web.Response:
        """Return a JSON response."""
        try:
            msg = json_bytes(result)
        except JSON_ENCODE_EXCEPTIONS as err:
            _LOGGER.error(
                "Unable to serialize to JSON. Bad data found at %s",
                format_unserializable_data(
                    find_paths_unserializable_data(result, dump=json_dumps)
                ),
            )
            raise HTTPInternalServerError from err
        response = web.Response(
            body=msg,
            content_type=CONTENT_TYPE_JSON,
            status=int(status_code),
            headers=headers,
        )
        response.enable_compression()
        return response

    def json_message(
        self,
        message: str,
        status_code: HTTPStatus | int = HTTPStatus.OK,
        message_code: str | None = None,
        headers: LooseHeaders | None = None,
    ) -> web.Response:
        """Return a JSON message response."""
        data = {"message": message}
        if message_code is not None:
            data["code"] = message_code
        return self.json(data, status_code, headers=headers)

    def register(
        self, hass: HomeAssistant, app: web.Application, router: web.UrlDispatcher
    ) -> None:
        """Register the view with a router."""
        assert self.url is not None, "No url set for view"
        urls = [self.url] + self.extra_urls
        routes: list[AbstractRoute] = []

        for method in ("get", "post", "delete", "put", "patch", "head", "options"):
            if not (handler := getattr(self, method, None)):
                continue

            handler = request_handler_factory(hass, self, handler)

            for url in urls:
                routes.append(router.add_route(method, url, handler))

        # Use `get` because CORS middleware is not be loaded in emulated_hue
        if self.cors_allowed:
            allow_cors = app.get("allow_all_cors")
        else:
            allow_cors = app.get("allow_configured_cors")

        if allow_cors:
            for route in routes:
                allow_cors(route)


def request_handler_factory(
    hass: HomeAssistant, view: HomeAssistantView, handler: Callable
) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
    """Wrap the handler classes."""
    is_coroutinefunction = asyncio.iscoroutinefunction(handler)
    assert is_coroutinefunction or is_callback(
        handler
    ), "Handler should be a coroutine or a callback."

    async def handle(request: web.Request) -> web.StreamResponse:
        """Handle incoming request."""
        if hass.is_stopping:
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        authenticated = request.get(KEY_AUTHENTICATED, False)

        if view.requires_auth and not authenticated:
            raise HTTPUnauthorized()

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Serving %s to %s (auth: %s)",
                request.path,
                request.remote,
                authenticated,
            )

        try:
            if is_coroutinefunction:
                result = await handler(request, **request.match_info)
            else:
                result = handler(request, **request.match_info)
        except vol.Invalid as err:
            raise HTTPBadRequest() from err
        except exceptions.ServiceNotFound as err:
            raise HTTPInternalServerError() from err
        except exceptions.Unauthorized as err:
            raise HTTPUnauthorized() from err

        if isinstance(result, web.StreamResponse):
            # The method handler returned a ready-made Response, how nice of it
            return result

        status_code = HTTPStatus.OK
        if isinstance(result, tuple):
            result, status_code = result

        if isinstance(result, bytes):
            return web.Response(body=result, status=status_code)

        if isinstance(result, str):
            return web.Response(text=result, status=status_code)

        if result is None:
            return web.Response(body=b"", status=status_code)

        raise TypeError(
            f"Result should be None, string, bytes or StreamResponse. Got: {result}"
        )

    return handle
