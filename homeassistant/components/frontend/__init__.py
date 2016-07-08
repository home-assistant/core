"""Handle the frontend for Home Assistant."""
import os

from homeassistant.components import api
from homeassistant.components.http import HomeAssistantView
from . import version, mdi_version

DOMAIN = 'frontend'
DEPENDENCIES = ['api']


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
        os.path.join(www_static_path, sw_path),
        0
    )
    hass.wsgi.register_static_path(
        "/robots.txt",
        os.path.join(www_static_path, "robots.txt")
    )
    hass.wsgi.register_static_path("/static", www_static_path)
    hass.wsgi.register_static_path("/local", hass.config.path('www'))

    return True


class BootstrapView(HomeAssistantView):
    """View to bootstrap frontend with all needed data."""

    url = "/api/bootstrap"
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

    url = '/'
    name = "frontend:index"
    requires_auth = False
    extra_urls = ['/logbook', '/history', '/map', '/devService', '/devState',
                  '/devEvent', '/devInfo', '/devTemplate',
                  '/states', '/states/<entity:entity_id>']

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
            core_url = 'home-assistant-polymer/build/_core_compiled.js'
            ui_url = 'home-assistant-polymer/src/home-assistant.html'
        else:
            core_url = 'core-{}.js'.format(version.CORE)
            ui_url = 'frontend-{}.html'.format(version.UI)

        # auto login if no password was set
        if self.hass.config.api.api_password is None:
            auth = 'true'
        else:
            auth = 'false'

        icons_url = 'mdi-{}.html'.format(mdi_version.VERSION)

        template = self.templates.get_template('index.html')

        # pylint is wrong
        # pylint: disable=no-member
        resp = template.render(
            core_url=core_url, ui_url=ui_url, auth=auth,
            icons_url=icons_url, icons=mdi_version.VERSION)

        return self.Response(resp, mimetype='text/html')
