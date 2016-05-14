"""Handle the frontend for Home Assistant."""
import re
import os
import logging

from . import version, mdi_version
from homeassistant.const import URL_ROOT
from homeassistant.components import api
from homeassistant.components.http import HomeAssistantView

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
    hass.wsgi.register_view(IndexView)
    hass.wsgi.register_view(BootstrapView)

    www_static_path = os.path.join(os.path.dirname(__file__), 'www_static')
    if hass.wsgi.development:
        sw_path = "home-assistant-polymer/build/service_worker.js"
    else:
        sw_path = "service_worker.js"

    hass.wsgi.register_static_path(
        "/service_worker.js",
        os.path.join(www_static_path, sw_path)
    )
    hass.wsgi.register_static_path("/static", www_static_path)
    hass.wsgi.register_static_path("/local", hass.config.path('www'))

    return True


class BootstrapView(HomeAssistantView):
    """View to bootstrap frontend with all needed data."""

    url = URL_API_BOOTSTRAP
    name = "api:bootstrap"

    def get(self, request):
        """Return all data needed to bootstrap Home Assistant."""
        return self.json({
            'config': self.hass.config.as_dict(),
            'states': self.hass.states.all(),
            'events': api.events_json(self.hass),
            'services': api.services_json(self.hass),
        })


class IndexView(HomeAssistantView):
    """Serve the frontend."""

    url = URL_ROOT
    name = "frontend:index"
    requires_auth = False
    extra_urls = ['/logbook', '/history', '/map', '/devService', '/devState',
                  '/devEvent', '/devInfo', '/devTemplate',
                  '/states', '/states/<entity_id>']

    def __init__(self, hass):
        """Initialize the frontend view."""
        super().__init__(hass)

        from jinja2 import FileSystemLoader, Environment

        self.templates = Environment(
            loader=FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates/')
            )
        )

    def get(self, request, entity_id=None):
        """Serve the index view."""
        if self.hass.wsgi.development:
            app_url = 'home-assistant-polymer/src/home-assistant.html'
        else:
            app_url = "frontend-{}.html".format(version.VERSION)

        # auto login if no password was set, else check api_password param
        if self.hass.config.api.api_password is None:
            auth = 'no_password_set'
        else:
            request.values.get('api_password', '')

        template = self.templates.get_template('index.html')

        resp = template.render(app_url=app_url, auth=auth,
                               icons=mdi_version.VERSION)

        return self.Response(resp, mimetype="text/html")
