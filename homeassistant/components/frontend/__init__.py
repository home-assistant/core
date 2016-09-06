"""Handle the frontend for Home Assistant."""
import hashlib
import logging
import os

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components import api
from homeassistant.components.http import HomeAssistantView
from .version import FINGERPRINTS

DOMAIN = 'frontend'
DEPENDENCIES = ['api']
URL_PANEL_COMPONENT = '/frontend/panels/{}.html'
URL_PANEL_COMPONENT_FP = '/frontend/panels/{}-{}.html'
STATIC_PATH = os.path.join(os.path.dirname(__file__), 'www_static')
PANELS = {}
MANIFEST_JSON = {
    "background_color": "#FFFFFF",
    "description": "Open-source home automation platform running on Python 3.",
    "dir": "ltr",
    "display": "standalone",
    "icons": [],
    "lang": "en-US",
    "name": "Home Assistant",
    "orientation": "any",
    "short_name": "Assistant",
    "start_url": "/",
    "theme_color": "#03A9F4"
}

# To keep track we don't register a component twice (gives a warning)
_REGISTERED_COMPONENTS = set()
_LOGGER = logging.getLogger(__name__)


def register_built_in_panel(hass, component_name, sidebar_title=None,
                            sidebar_icon=None, url_path=None, config=None):
    """Register a built-in panel."""
    # pylint: disable=too-many-arguments
    path = 'panels/ha-panel-{}.html'.format(component_name)

    if hass.wsgi.development:
        url = ('/static/home-assistant-polymer/panels/'
               '{0}/ha-panel-{0}.html'.format(component_name))
    else:
        url = None  # use default url generate mechanism

    register_panel(hass, component_name, os.path.join(STATIC_PATH, path),
                   FINGERPRINTS[path], sidebar_title, sidebar_icon, url_path,
                   url, config)


def register_panel(hass, component_name, path, md5=None, sidebar_title=None,
                   sidebar_icon=None, url_path=None, url=None, config=None):
    """Register a panel for the frontend.

    component_name: name of the web component
    path: path to the HTML of the web component
    md5: the md5 hash of the web component (for versioning, optional)
    sidebar_title: title to show in the sidebar (optional)
    sidebar_icon: icon to show next to title in sidebar (optional)
    url_path: name to use in the url (defaults to component_name)
    url: for the web component (for dev environment, optional)
    config: config to be passed into the web component

    Warning: this API will probably change. Use at own risk.
    """
    # pylint: disable=too-many-arguments
    if url_path is None:
        url_path = component_name

    if url_path in PANELS:
        _LOGGER.warning('Overwriting component %s', url_path)
    if not os.path.isfile(path):
        _LOGGER.error('Panel %s component does not exist: %s',
                      component_name, path)
        return

    if md5 is None:
        with open(path) as fil:
            md5 = hashlib.md5(fil.read().encode('utf-8')).hexdigest()

    data = {
        'url_path': url_path,
        'component_name': component_name,
    }

    if sidebar_title:
        data['title'] = sidebar_title
    if sidebar_icon:
        data['icon'] = sidebar_icon
    if config is not None:
        data['config'] = config

    if url is not None:
        data['url'] = url
    else:
        url = URL_PANEL_COMPONENT.format(component_name)

        if url not in _REGISTERED_COMPONENTS:
            hass.wsgi.register_static_path(url, path)
            _REGISTERED_COMPONENTS.add(url)

        fprinted_url = URL_PANEL_COMPONENT_FP.format(component_name, md5)
        data['url'] = fprinted_url

    PANELS[url_path] = data


def add_manifest_json_key(key, val):
    """Add a keyval to the manifest.json."""
    MANIFEST_JSON[key] = val


def setup(hass, config):
    """Setup serving the frontend."""
    hass.wsgi.register_view(BootstrapView)
    hass.wsgi.register_view(ManifestJSONView)

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

    for size in (192, 384, 512, 1024):
        MANIFEST_JSON['icons'].append({
            "src": "/static/icons/favicon-{}x{}.png".format(size, size),
            "sizes": "{}x{}".format(size, size),
            "type": "image/png"
        })

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

        if request.path == '/':
            panel = 'states'
        else:
            panel = request.path.split('/')[1]

        panel_url = PANELS[panel]['url'] if panel != 'states' else ''

        # auto login if no password was set
        no_auth = 'false' if self.hass.config.api.api_password else 'true'

        icons_url = '/static/mdi-{}.html'.format(FINGERPRINTS['mdi.html'])
        template = self.templates.get_template('index.html')

        # pylint is wrong
        # pylint: disable=no-member
        resp = template.render(
            core_url=core_url, ui_url=ui_url, no_auth=no_auth,
            icons_url=icons_url, icons=FINGERPRINTS['mdi.html'],
            panel_url=panel_url, panels=PANELS)

        return self.Response(resp, mimetype='text/html')


class ManifestJSONView(HomeAssistantView):
    """View to return a manifest.json."""

    requires_auth = False
    url = "/manifest.json"
    name = "manifestjson"

    def get(self, request):
        """Return the manifest.json."""
        import json
        msg = json.dumps(MANIFEST_JSON, sort_keys=True).encode('UTF-8')
        return self.Response(msg, mimetype="application/manifest+json")
