"""
This module provides WSGI application to serve the Home Assistant API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/http/
"""
import asyncio
import json
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized

import homeassistant.remote as rem
from homeassistant.core import is_callback
from homeassistant.const import CONTENT_TYPE_JSON

from .const import KEY_AUTHENTICATED, KEY_REAL_IP


_LOGGER = logging.getLogger(__name__)


class HomeAssistantView(object):
    """Base view for all views."""

    url = None
    extra_urls = []
    requires_auth = True  # Views inheriting from this class can override this

    # pylint: disable=no-self-use
    def json(self, result, status_code=200, headers=None):
        """Return a JSON response."""
        msg = json.dumps(
            result, sort_keys=True, cls=rem.JSONEncoder).encode('UTF-8')
        response = web.Response(
            body=msg, content_type=CONTENT_TYPE_JSON, status=status_code,
            headers=headers)
        response.enable_compression()
        return response

    def json_message(self, message, status_code=200, message_code=None,
                     headers=None):
        """Return a JSON message response."""
        data = {'message': message}
        if message_code is not None:
            data['code'] = message_code
        return self.json(data, status_code, headers=headers)

    # pylint: disable=no-self-use
    async def file(self, request, fil):
        """Return a file."""
        assert isinstance(fil, str), 'only string paths allowed'
        return web.FileResponse(fil)

    def register(self, router):
        """Register the view with a router."""
        assert self.url is not None, 'No url set for view'
        urls = [self.url] + self.extra_urls

        for method in ('get', 'post', 'delete', 'put'):
            handler = getattr(self, method, None)

            if not handler:
                continue

            handler = request_handler_factory(self, handler)

            for url in urls:
                router.add_route(method, url, handler)

        # aiohttp_cors does not work with class based views
        # self.app.router.add_route('*', self.url, self, name=self.name)

        # for url in self.extra_urls:
        #     self.app.router.add_route('*', url, self)


def request_handler_factory(view, handler):
    """Wrap the handler classes."""
    assert asyncio.iscoroutinefunction(handler) or is_callback(handler), \
        "Handler should be a coroutine or a callback."

    async def handle(request):
        """Handle incoming request."""
        if not request.app['hass'].is_running:
            return web.Response(status=503)

        authenticated = request.get(KEY_AUTHENTICATED, False)

        if view.requires_auth and not authenticated:
            raise HTTPUnauthorized()

        _LOGGER.info('Serving %s to %s (auth: %s)',
                     request.path, request.get(KEY_REAL_IP), authenticated)

        result = handler(request, **request.match_info)

        if asyncio.iscoroutine(result):
            result = await result

        if isinstance(result, web.StreamResponse):
            # The method handler returned a ready-made Response, how nice of it
            return result

        status_code = 200

        if isinstance(result, tuple):
            result, status_code = result

        if isinstance(result, str):
            result = result.encode('utf-8')
        elif result is None:
            result = b''
        elif not isinstance(result, bytes):
            assert False, ('Result should be None, string, bytes or Response. '
                           'Got: {}').format(result)

        return web.Response(body=result, status=status_code)

    return handle
