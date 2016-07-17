"""Handle the frontend for Home Assistant."""
import logging
import os

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components import api
from homeassistant.components.http import HomeAssistantView
from .version import FINGERPRINTS

DOMAIN = 'frontend'
DEPENDENCIES = ['api']
PANELS = {}
URL_PANEL_COMPONENT = '/frontend/panels/{}.html'
URL_PANEL_COMPONENT_FP = '/frontend/panels/{}-{}.html'
STATIC_PATH = os.path.join(os.path.dirname(__file__), 'www_static')
_LOGGER = logging.getLogger(__name__)


def register_built_in_panel(hass, component_name, title=None, icon=None,
                            url_name=None, config=None):
    """Register a built-in panel."""

    path = 'panels/ha-panel-{}.html'.format(component_name)

    register_panel(hass, component_name, os.path.join(STATIC_PATH, path),
                   FINGERPRINTS[path], title, icon, url_name, config)


def register_panel(hass, component_name, path, md5, title=None, icon=None,
                   url_name=None, config=None):
    """Register a panel for the frontend.

    component_name: name of the web component
    path: path to the HTML of the web component
    md5: the md5 hash of the web component (for versioning)
    title: title to show in the sidebar (optional)
    icon: icon to show next to title in sidebar (optional)
    url_name: name to use in the url (defaults to component_name)
    config: config to be passed into the web component

    Warning: this API will probably change. Use at own risk.
    """
    if url_name is None:
        url_name = component_name

    if url_name in PANELS:
        _LOGGER.warning('Overwriting component %s', url_name)
    if not os.path.isfile(path):
        _LOGGER.warning('Panel %s component does not exist: %s',
                        component_name, path)

    data = {
        'url_name': url_name,
        'component_name': component_name,
    }

    if title:
        data['title'] = title
    if icon:
        data['icon'] = icon
    if config is not None:
        data['config'] = config

    if hass.wsgi.development:
        data['url'] = ('/static/home-assistant-polymer/panels/'
                       '{0}/ha-panel-{0}.html'.format(component_name))
    else:
        url = URL_PANEL_COMPONENT.format(component_name)
        fprinted_url = URL_PANEL_COMPONENT_FP.format(component_name, md5)
        hass.wsgi.register_static_path(url, path)
        data['url'] = fprinted_url

    PANELS[url_name] = data

    # TODO register /<component_name> to index view.


def setup(hass, config):
    """Setup serving the frontend."""
    hass.wsgi.register_view(BootstrapView)

    if hass.wsgi.development:
        sw_path = "home-assistant-polymer/build/service_worker.js"
    else:
        sw_path = "service_worker.js"

    hass.wsgi.register_static_path("/service_worker.js",
                                   os.path.join(STATIC_PATH, sw_path), 0)
    hass.wsgi.register_static_path("/robots.txt",
                                   os.path.join(STATIC_PATH, "robots.txt"))
    hass.wsgi.register_static_path("/static", STATIC_PATH)
    hass.wsgi.register_static_path("/local", hass.config.path('www'))

    register_built_in_panel(hass, 'map', 'Map', 'mdi:account-location')

    for panel in ('dev-event', 'dev-info', 'dev-service', 'dev-state',
                  'dev-template'):
        register_built_in_panel(hass, panel)

    def register_frontend_index(event):
        """Register the frontend index urls.

        Done when Home Assistant is started so that all panels are known.
        """
        hass.wsgi.register_view(IndexView(
            hass, ['/{}'.format(name) for name in PANELS]))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, register_frontend_index)

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
            'panels': PANELS,
        })


class IndexView(HomeAssistantView):
    """Serve the frontend."""

    url = '/'
    name = "frontend:index"
    requires_auth = False
    extra_urls = ['/states', '/states/<entity:entity_id>']

    def __init__(self, hass, extra_urls):
        """Initialize the frontend view."""
        super().__init__(hass)

        from jinja2 import FileSystemLoader, Environment

        self.extra_urls = self.extra_urls + extra_urls
        self.templates = Environment(
            loader=FileSystemLoader(
                os.path.join(os.path.dirname(__file__), 'templates/')
            )
        )

    def get(self, request, entity_id=None):
        """Serve the index view."""
        if self.hass.wsgi.development:
            core_url = '/static/home-assistant-polymer/build/core.js'
            ui_url = '/static/home-assistant-polymer/src/home-assistant.html'
        else:
            core_url = '/static/core-{}.js'.format(
                FINGERPRINTS['core.js'])
            ui_url = '/static/frontend-{}.html'.format(
                FINGERPRINTS['frontend.html'])

        # auto login if no password was set
        no_auth = 'false' if self.hass.config.api.api_password else 'true'

        icons_url = '/static/mdi-{}.html'.format(FINGERPRINTS['mdi.html'])
        template = self.templates.get_template('index.html')

        # pylint is wrong
        # pylint: disable=no-member
        resp = template.render(
            core_url=core_url, ui_url=ui_url, no_auth=no_auth,
            icons_url=icons_url, icons=FINGERPRINTS['mdi.html'])

        return self.Response(resp, mimetype='text/html')
