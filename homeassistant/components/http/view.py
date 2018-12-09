"""
This module provides WSGI application to serve the Home Assistant API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/http/
"""
import asyncio
import json
import logging

from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPUnauthorized, HTTPInternalServerError, HTTPBadRequest)
import voluptuous as vol

from homeassistant.components.http.ban import process_success_login
from homeassistant.core import Context, is_callback
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant import exceptions
from homeassistant.helpers.json import JSONEncoder

from .const import KEY_AUTHENTICATED, KEY_REAL_IP


_LOGGER = logging.getLogger(__name__)


class HomeAssistantView:
    """Base view for all views."""

    url = None
    extra_urls = []
    # Views inheriting from this class can override this
    requires_auth = True
    cors_allowed = False

    # pylint: disable=no-self-use
    def context(self, request):
        """Generate a context from a request."""
        user = request.get('hass_user')
        if user is None:
            return Context()

        return Context(user_id=user.id)

    def json(self, result, status_code=200, headers=None):
        """Return a JSON response."""
        try:
            msg = json.dumps(
                result, sort_keys=True, cls=JSONEncoder, allow_nan=False
            ).encode('UTF-8')
        except (ValueError, TypeError) as err:
            _LOGGER.error('Unable to serialize to JSON: %s\n%s', err, result)
            raise HTTPInternalServerError
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

    def register(self, app, router):
        """Register the view with a router."""
        assert self.url is not None, 'No url set for view'
        urls = [self.url] + self.extra_urls
        routes = []

        for method in ('get', 'post', 'delete', 'put'):
            handler = getattr(self, method, None)

            if not handler:
                continue

            handler = request_handler_factory(self, handler)

            for url in urls:
                routes.append(router.add_route(method, url, handler))

        if not self.cors_allowed:
            return

        for route in routes:
            app['allow_cors'](route)


def request_handler_factory(view, handler):
    """Wrap the handler classes."""
    assert asyncio.iscoroutinefunction(handler) or is_callback(handler), \
        "Handler should be a coroutine or a callback."

    async def handle(request):
        """Handle incoming request."""
        if not request.app['hass'].is_running:
            return web.Response(status=503)

        authenticated = request.get(KEY_AUTHENTICATED, False)

        if view.requires_auth:
            if authenticated:
                await process_success_login(request)
            else:
                raise HTTPUnauthorized()

        _LOGGER.info('Serving %s to %s (auth: %s)',
                     request.path, request.get(KEY_REAL_IP), authenticated)

        try:
            result = handler(request, **request.match_info)

            if asyncio.iscoroutine(result):
                result = await result
        except vol.Invalid:
            raise HTTPBadRequest()
        except exceptions.ServiceNotFound:
            raise HTTPInternalServerError()
        except exceptions.Unauthorized:
            raise HTTPUnauthorized()

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
