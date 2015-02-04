"""
homeassistant.components.frontend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides a frontend for Home Assistant.
"""
import re
import os
import logging

from . import version
import homeassistant.util as util

DOMAIN = 'frontend'
DEPENDENCIES = ['api']

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422


URL_ROOT = "/"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Setup serving the frontend. """
    if 'http' not in hass.components:
        _LOGGER.error('Dependency http is not loaded')
        return False

    hass.http.register_path('GET', URL_ROOT, _handle_get_root, False)

    # Static files
    hass.http.register_path(
        'GET', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)
    hass.http.register_path(
        'HEAD', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)

    return True


def _handle_get_root(handler, path_match, data):
    """ Renders the debug interface. """

    write = lambda txt: handler.wfile.write((txt + "\n").encode("UTF-8"))

    handler.send_response(HTTP_OK)
    handler.send_header('Content-type', 'text/html; charset=utf-8')
    handler.end_headers()

    if handler.server.development:
        app_url = "polymer/home-assistant.html"
    else:
        app_url = "frontend-{}.html".format(version.VERSION)

    # auto login if no password was set, else check api_password param
    auth = (handler.server.api_password if handler.server.no_password_set
            else data.get('api_password', ''))

    write(("<!doctype html>"
           "<html>"
           "<head><title>Home Assistant</title>"
           "<meta name='mobile-web-app-capable' content='yes'>"
           "<link rel='shortcut icon' href='/static/favicon.ico' />"
           "<link rel='icon' type='image/png' "
           "     href='/static/favicon-192x192.png' sizes='192x192'>"
           "<meta name='viewport' content='width=device-width, "
           "      user-scalable=no, initial-scale=1.0, "
           "      minimum-scale=1.0, maximum-scale=1.0' />"
           "<meta name='theme-color' content='#03a9f4'>"
           "</head>"
           "<body fullbleed>"
           "<h3 id='init' align='center'>Initializing Home Assistant</h3>"
           "<script"
           "     src='/static/webcomponents.min.js'></script>"
           "<link rel='import' href='/static/{}' />"
           "<home-assistant auth='{}'></home-assistant>"
           "</body></html>").format(app_url, auth))


def _handle_get_static(handler, path_match, data):
    """ Returns a static file for the frontend. """
    req_file = util.sanitize_path(path_match.group('file'))

    # Strip md5 hash out of frontend filename
    if re.match(r'^frontend-[A-Za-z0-9]{32}\.html$', req_file):
        req_file = "frontend.html"

    path = os.path.join(os.path.dirname(__file__), 'www_static', req_file)

    handler.write_file(path)
