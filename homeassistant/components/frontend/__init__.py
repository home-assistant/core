"""Handle the frontend for Home Assistant."""
import re
import os
import logging

from . import version, mdi_version
import homeassistant.util as util
from homeassistant.const import URL_ROOT, HTTP_OK
from homeassistant.components import api

DOMAIN = 'frontend'
DEPENDENCIES = ['api']

INDEX_PATH = os.path.join(os.path.dirname(__file__), 'index.html.template')

_LOGGER = logging.getLogger(__name__)

FRONTEND_URLS = [
    URL_ROOT, '/logbook', '/history', '/map', '/devService', '/devState',
    '/devEvent', '/devInfo', '/devTemplate',
    re.compile(r'/states(/([a-zA-Z\._\-0-9/]+)|)'),
]

URL_API_BOOTSTRAP = "/api/bootstrap"

_FINGERPRINT = re.compile(r'^(\w+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)


def setup(hass, config):
    """Setup serving the frontend."""
    for url in FRONTEND_URLS:
        hass.http.register_path('GET', url, _handle_get_root, False)

    hass.http.register_path('GET', '/service_worker.js',
                            _handle_get_service_worker, False)

    # Bootstrap API
    hass.http.register_path(
        'GET', URL_API_BOOTSTRAP, _handle_get_api_bootstrap)

    # Static files
    hass.http.register_path(
        'GET', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)
    hass.http.register_path(
        'HEAD', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_static, False)
    hass.http.register_path(
        'GET', re.compile(r'/local/(?P<file>[a-zA-Z\._\-0-9/]+)'),
        _handle_get_local, False)

    return True


def _handle_get_api_bootstrap(handler, path_match, data):
    """Return all data needed to bootstrap Home Assistant."""
    hass = handler.server.hass

    handler.write_json({
        'config': hass.config.as_dict(),
        'states': hass.states.all(),
        'events': api.events_json(hass),
        'services': api.services_json(hass),
    })


def _handle_get_root(handler, path_match, data):
    """Render the frontend."""
    if handler.server.development:
        app_url = "home-assistant-polymer/src/home-assistant.html"
    else:
        app_url = "frontend-{}.html".format(version.VERSION)

    # auto login if no password was set, else check api_password param
    auth = ('no_password_set' if handler.server.api_password is None
            else data.get('api_password', ''))

    with open(INDEX_PATH) as template_file:
        template_html = template_file.read()

    template_html = template_html.replace('{{ app_url }}', app_url)
    template_html = template_html.replace('{{ auth }}', auth)
    template_html = template_html.replace('{{ icons }}', mdi_version.VERSION)

    handler.send_response(HTTP_OK)
    handler.write_content(template_html.encode("UTF-8"),
                          'text/html; charset=utf-8')


def _handle_get_service_worker(handler, path_match, data):
    """Return service worker for the frontend."""
    if handler.server.development:
        sw_path = "home-assistant-polymer/build/service_worker.js"
    else:
        sw_path = "service_worker.js"

    handler.write_file(os.path.join(os.path.dirname(__file__), 'www_static',
                                    sw_path))


def _handle_get_static(handler, path_match, data):
    """Return a static file for the frontend."""
    req_file = util.sanitize_path(path_match.group('file'))

    # Strip md5 hash out
    fingerprinted = _FINGERPRINT.match(req_file)
    if fingerprinted:
        req_file = "{}.{}".format(*fingerprinted.groups())

    path = os.path.join(os.path.dirname(__file__), 'www_static', req_file)

    handler.write_file(path)


def _handle_get_local(handler, path_match, data):
    """Return a static file from the hass.config.path/www for the frontend."""
    req_file = util.sanitize_path(path_match.group('file'))

    path = handler.server.hass.config.path('www', req_file)

    handler.write_file(path)
