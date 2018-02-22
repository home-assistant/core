"""
Handle the frontend for Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/frontend/
"""
import asyncio
import hashlib
import json
import logging
import os
from urllib.parse import urlparse

from aiohttp import web
import voluptuous as vol
import jinja2

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.config import find_config_file, load_yaml_config_file
from homeassistant.const import CONF_NAME, EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.loader import bind_hass

REQUIREMENTS = ['home-assistant-frontend==20180221.1', 'user-agents==1.1.0']

DOMAIN = 'frontend'
DEPENDENCIES = ['api', 'websocket_api', 'http', 'system_log']

URL_PANEL_COMPONENT_FP = '/frontend/panels/{}-{}.html'

CONF_THEMES = 'themes'
CONF_EXTRA_HTML_URL = 'extra_html_url'
CONF_EXTRA_HTML_URL_ES5 = 'extra_html_url_es5'
CONF_FRONTEND_REPO = 'development_repo'
CONF_JS_VERSION = 'javascript_version'
JS_DEFAULT_OPTION = 'auto'
JS_OPTIONS = ['es5', 'latest', 'auto']

DEFAULT_THEME_COLOR = '#03A9F4'

MANIFEST_JSON = {
    'background_color': '#FFFFFF',
    'description': 'Open-source home automation platform running on Python 3.',
    'dir': 'ltr',
    'display': 'standalone',
    'icons': [],
    'lang': 'en-US',
    'name': 'Home Assistant',
    'short_name': 'Assistant',
    'start_url': '/states',
    'theme_color': DEFAULT_THEME_COLOR
}

for size in (192, 384, 512, 1024):
    MANIFEST_JSON['icons'].append({
        'src': '/static/icons/favicon-{}x{}.png'.format(size, size),
        'sizes': '{}x{}'.format(size, size),
        'type': 'image/png'
    })

DATA_FINALIZE_PANEL = 'frontend_finalize_panel'
DATA_PANELS = 'frontend_panels'
DATA_JS_VERSION = 'frontend_js_version'
DATA_EXTRA_HTML_URL = 'frontend_extra_html_url'
DATA_EXTRA_HTML_URL_ES5 = 'frontend_extra_html_url_es5'
DATA_THEMES = 'frontend_themes'
DATA_DEFAULT_THEME = 'frontend_default_theme'
DEFAULT_THEME = 'default'

PRIMARY_COLOR = 'primary-color'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_FRONTEND_REPO): cv.isdir,
        vol.Optional(CONF_THEMES): vol.Schema({
            cv.string: {cv.string: cv.string}
        }),
        vol.Optional(CONF_EXTRA_HTML_URL):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXTRA_HTML_URL_ES5):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_JS_VERSION, default=JS_DEFAULT_OPTION):
            vol.In(JS_OPTIONS)
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_SET_THEME = 'set_theme'
SERVICE_RELOAD_THEMES = 'reload_themes'
SERVICE_SET_THEME_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})


class AbstractPanel:
    """Abstract class for panels."""

    # Name of the webcomponent
    component_name = None

    # Icon to show in the sidebar (optional)
    sidebar_icon = None

    # Title to show in the sidebar (optional)
    sidebar_title = None

    # Url to the webcomponent (depending on JS version)
    webcomponent_url_es5 = None
    webcomponent_url_latest = None

    # Url to show the panel in the frontend
    frontend_url_path = None

    # Config to pass to the webcomponent
    config = None

    @asyncio.coroutine
    def async_register(self, hass):
        """Register panel with HASS."""
        panels = hass.data.get(DATA_PANELS)
        if panels is None:
            panels = hass.data[DATA_PANELS] = {}

        if self.frontend_url_path in panels:
            _LOGGER.warning("Overwriting component %s", self.frontend_url_path)

        if DATA_FINALIZE_PANEL in hass.data:
            yield from hass.data[DATA_FINALIZE_PANEL](self)

        panels[self.frontend_url_path] = self

    @callback
    def async_register_index_routes(self, router, index_view):
        """Register routes for panel to be served by index view."""
        router.add_route(
            'get', '/{}'.format(self.frontend_url_path), index_view.get)
        router.add_route(
            'get', '/{}/{{extra:.+}}'.format(self.frontend_url_path),
            index_view.get)

    def to_response(self, hass, request):
        """Panel as dictionary."""
        result = {
            'component_name': self.component_name,
            'icon': self.sidebar_icon,
            'title': self.sidebar_title,
            'url_path': self.frontend_url_path,
            'config': self.config,
        }
        if _is_latest(hass.data[DATA_JS_VERSION], request):
            result['url'] = self.webcomponent_url_latest
        else:
            result['url'] = self.webcomponent_url_es5
        return result


class BuiltInPanel(AbstractPanel):
    """Panel that is part of hass_frontend."""

    def __init__(self, component_name, sidebar_title, sidebar_icon,
                 frontend_url_path, config):
        """Initialize a built-in panel."""
        self.component_name = component_name
        self.sidebar_title = sidebar_title
        self.sidebar_icon = sidebar_icon
        self.frontend_url_path = frontend_url_path or component_name
        self.config = config

    @asyncio.coroutine
    def async_finalize(self, hass, frontend_repository_path):
        """Finalize this panel for usage.

        If frontend_repository_path is set, will be prepended to path of
        built-in components.
        """
        if frontend_repository_path is None:
            import hass_frontend
            import hass_frontend_es5

            self.webcomponent_url_latest = \
                '/frontend_latest/panels/ha-panel-{}-{}.html'.format(
                    self.component_name,
                    hass_frontend.FINGERPRINTS[self.component_name])
            self.webcomponent_url_es5 = \
                '/frontend_es5/panels/ha-panel-{}-{}.html'.format(
                    self.component_name,
                    hass_frontend_es5.FINGERPRINTS[self.component_name])
        else:
            # Dev mode
            self.webcomponent_url_es5 = self.webcomponent_url_latest = \
                '/home-assistant-polymer/panels/{}/ha-panel-{}.html'.format(
                    self.component_name, self.component_name)


class ExternalPanel(AbstractPanel):
    """Panel that is added by a custom component."""

    REGISTERED_COMPONENTS = set()

    def __init__(self, component_name, path, md5, sidebar_title, sidebar_icon,
                 frontend_url_path, config):
        """Initialize an external panel."""
        self.component_name = component_name
        self.path = path
        self.md5 = md5
        self.sidebar_title = sidebar_title
        self.sidebar_icon = sidebar_icon
        self.frontend_url_path = frontend_url_path or component_name
        self.config = config

    @asyncio.coroutine
    def async_finalize(self, hass, frontend_repository_path):
        """Finalize this panel for usage.

        frontend_repository_path is set, will be prepended to path of built-in
        components.
        """
        try:
            if self.md5 is None:
                self.md5 = yield from hass.async_add_job(
                    _fingerprint, self.path)
        except OSError:
            _LOGGER.error('Cannot find or access %s at %s',
                          self.component_name, self.path)
            hass.data[DATA_PANELS].pop(self.frontend_url_path)
            return

        self.webcomponent_url_es5 = self.webcomponent_url_latest = \
            URL_PANEL_COMPONENT_FP.format(self.component_name, self.md5)

        if self.component_name not in self.REGISTERED_COMPONENTS:
            hass.http.register_static_path(
                self.webcomponent_url_latest, self.path,
                # if path is None, we're in prod mode, so cache static assets
                frontend_repository_path is None)
            self.REGISTERED_COMPONENTS.add(self.component_name)


@bind_hass
@asyncio.coroutine
def async_register_built_in_panel(hass, component_name, sidebar_title=None,
                                  sidebar_icon=None, frontend_url_path=None,
                                  config=None):
    """Register a built-in panel."""
    panel = BuiltInPanel(component_name, sidebar_title, sidebar_icon,
                         frontend_url_path, config)
    yield from panel.async_register(hass)


@bind_hass
@asyncio.coroutine
def async_register_panel(hass, component_name, path, md5=None,
                         sidebar_title=None, sidebar_icon=None,
                         frontend_url_path=None, config=None):
    """Register a panel for the frontend.

    component_name: name of the web component
    path: path to the HTML of the web component
          (required unless url is provided)
    md5: the md5 hash of the web component (for versioning in URL, optional)
    sidebar_title: title to show in the sidebar (optional)
    sidebar_icon: icon to show next to title in sidebar (optional)
    url_path: name to use in the URL (defaults to component_name)
    config: config to be passed into the web component
    """
    panel = ExternalPanel(component_name, path, md5, sidebar_title,
                          sidebar_icon, frontend_url_path, config)
    yield from panel.async_register(hass)


@bind_hass
@callback
def add_extra_html_url(hass, url, es5=False):
    """Register extra html url to load."""
    key = DATA_EXTRA_HTML_URL_ES5 if es5 else DATA_EXTRA_HTML_URL
    url_set = hass.data.get(key)
    if url_set is None:
        url_set = hass.data[key] = set()
    url_set.add(url)


def add_manifest_json_key(key, val):
    """Add a keyval to the manifest.json."""
    MANIFEST_JSON[key] = val


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the serving of the frontend."""
    hass.http.register_view(ManifestJSONView)

    conf = config.get(DOMAIN, {})

    repo_path = conf.get(CONF_FRONTEND_REPO)
    is_dev = repo_path is not None
    hass.data[DATA_JS_VERSION] = js_version = conf.get(CONF_JS_VERSION)

    if is_dev:
        for subpath in ["src", "build-translations", "build-temp", "build",
                        "hass_frontend", "bower_components", "panels",
                        "hassio"]:
            hass.http.register_static_path(
                "/home-assistant-polymer/{}".format(subpath),
                os.path.join(repo_path, subpath),
                False)

        hass.http.register_static_path(
            "/static/translations",
            os.path.join(repo_path, "build-translations/output"), False)
        sw_path_es5 = os.path.join(repo_path, "build-es5/service_worker.js")
        sw_path_latest = os.path.join(repo_path, "build/service_worker.js")
        static_path = os.path.join(repo_path, 'hass_frontend')
        frontend_es5_path = os.path.join(repo_path, 'build-es5')
        frontend_latest_path = os.path.join(repo_path, 'build')
    else:
        import hass_frontend
        import hass_frontend_es5
        sw_path_es5 = os.path.join(hass_frontend_es5.where(),
                                   "service_worker.js")
        sw_path_latest = os.path.join(hass_frontend.where(),
                                      "service_worker.js")
        # /static points to dir with files that are JS-type agnostic.
        # ES5 files are served from /frontend_es5.
        # ES6 files are served from /frontend_latest.
        static_path = hass_frontend.where()
        frontend_es5_path = hass_frontend_es5.where()
        frontend_latest_path = static_path

    hass.http.register_static_path(
        "/service_worker_es5.js", sw_path_es5, False)
    hass.http.register_static_path(
        "/service_worker.js", sw_path_latest, False)
    hass.http.register_static_path(
        "/robots.txt", os.path.join(static_path, "robots.txt"), not is_dev)
    hass.http.register_static_path("/static", static_path, not is_dev)
    hass.http.register_static_path(
        "/frontend_latest", frontend_latest_path, not is_dev)
    hass.http.register_static_path(
        "/frontend_es5", frontend_es5_path, not is_dev)

    local = hass.config.path('www')
    if os.path.isdir(local):
        hass.http.register_static_path("/local", local, not is_dev)

    index_view = IndexView(repo_path, js_version)
    hass.http.register_view(index_view)

    @asyncio.coroutine
    def finalize_panel(panel):
        """Finalize setup of a panel."""
        yield from panel.async_finalize(hass, repo_path)
        panel.async_register_index_routes(hass.http.app.router, index_view)

    yield from asyncio.wait([
        async_register_built_in_panel(hass, panel)
        for panel in ('dev-event', 'dev-info', 'dev-service', 'dev-state',
                      'dev-template', 'dev-mqtt', 'kiosk')], loop=hass.loop)

    hass.data[DATA_FINALIZE_PANEL] = finalize_panel

    # Finalize registration of panels that registered before frontend was setup
    # This includes the built-in panels from line above.
    yield from asyncio.wait(
        [finalize_panel(panel) for panel in hass.data[DATA_PANELS].values()],
        loop=hass.loop)

    if DATA_EXTRA_HTML_URL not in hass.data:
        hass.data[DATA_EXTRA_HTML_URL] = set()
    if DATA_EXTRA_HTML_URL_ES5 not in hass.data:
        hass.data[DATA_EXTRA_HTML_URL_ES5] = set()

    for url in conf.get(CONF_EXTRA_HTML_URL, []):
        add_extra_html_url(hass, url, False)
    for url in conf.get(CONF_EXTRA_HTML_URL_ES5, []):
        add_extra_html_url(hass, url, True)

    async_setup_themes(hass, conf.get(CONF_THEMES))

    return True


def async_setup_themes(hass, themes):
    """Set up themes data and services."""
    hass.http.register_view(ThemesView)
    hass.data[DATA_DEFAULT_THEME] = DEFAULT_THEME
    if themes is None:
        hass.data[DATA_THEMES] = {}
        return

    hass.data[DATA_THEMES] = themes

    @callback
    def update_theme_and_fire_event():
        """Update theme_color in manifest."""
        name = hass.data[DATA_DEFAULT_THEME]
        themes = hass.data[DATA_THEMES]
        if name != DEFAULT_THEME and PRIMARY_COLOR in themes[name]:
            MANIFEST_JSON['theme_color'] = themes[name][PRIMARY_COLOR]
        else:
            MANIFEST_JSON['theme_color'] = DEFAULT_THEME_COLOR
        hass.bus.async_fire(EVENT_THEMES_UPDATED, {
            'themes': themes,
            'default_theme': name,
        })

    @callback
    def set_theme(call):
        """Set backend-preferred theme."""
        data = call.data
        name = data[CONF_NAME]
        if name == DEFAULT_THEME or name in hass.data[DATA_THEMES]:
            _LOGGER.info("Theme %s set as default", name)
            hass.data[DATA_DEFAULT_THEME] = name
            update_theme_and_fire_event()
        else:
            _LOGGER.warning("Theme %s is not defined.", name)

    @callback
    def reload_themes(_):
        """Reload themes."""
        path = find_config_file(hass.config.config_dir)
        new_themes = load_yaml_config_file(path)[DOMAIN].get(CONF_THEMES, {})
        hass.data[DATA_THEMES] = new_themes
        if hass.data[DATA_DEFAULT_THEME] not in new_themes:
            hass.data[DATA_DEFAULT_THEME] = DEFAULT_THEME
        update_theme_and_fire_event()

    hass.services.async_register(
        DOMAIN, SERVICE_SET_THEME, set_theme, schema=SERVICE_SET_THEME_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RELOAD_THEMES, reload_themes)


class IndexView(HomeAssistantView):
    """Serve the frontend."""

    url = '/'
    name = 'frontend:index'
    requires_auth = False
    extra_urls = ['/states', '/states/{extra}']

    def __init__(self, repo_path, js_option):
        """Initialize the frontend view."""
        self.repo_path = repo_path
        self.js_option = js_option
        self._template_cache = {}

    def get_template(self, latest):
        """Get template."""
        if self.repo_path is not None:
            root = self.repo_path
        elif latest:
            import hass_frontend
            root = hass_frontend.where()
        else:
            import hass_frontend_es5
            root = hass_frontend_es5.where()

        tpl = self._template_cache.get(root)

        if tpl is None:
            with open(os.path.join(root, 'index.html')) as file:
                tpl = jinja2.Template(file.read())

            # Cache template if not running from repository
            if self.repo_path is None:
                self._template_cache[root] = tpl

        return tpl

    @asyncio.coroutine
    def get(self, request, extra=None):
        """Serve the index view."""
        hass = request.app['hass']
        latest = self.repo_path is not None or \
            _is_latest(self.js_option, request)

        if request.path == '/':
            panel = 'states'
        else:
            panel = request.path.split('/')[1]

        if panel == 'states':
            panel_url = ''
        elif latest:
            panel_url = hass.data[DATA_PANELS][panel].webcomponent_url_latest
        else:
            panel_url = hass.data[DATA_PANELS][panel].webcomponent_url_es5

        no_auth = '1'
        if hass.config.api.api_password and not request[KEY_AUTHENTICATED]:
            # do not try to auto connect on load
            no_auth = '0'

        template = yield from hass.async_add_job(self.get_template, latest)

        extra_key = DATA_EXTRA_HTML_URL if latest else DATA_EXTRA_HTML_URL_ES5

        resp = template.render(
            no_auth=no_auth,
            panel_url=panel_url,
            panels=hass.data[DATA_PANELS],
            theme_color=MANIFEST_JSON['theme_color'],
            extra_urls=hass.data[extra_key],
        )

        return web.Response(text=resp, content_type='text/html')


class ManifestJSONView(HomeAssistantView):
    """View to return a manifest.json."""

    requires_auth = False
    url = '/manifest.json'
    name = 'manifestjson'

    @asyncio.coroutine
    def get(self, request):    # pylint: disable=no-self-use
        """Return the manifest.json."""
        msg = json.dumps(MANIFEST_JSON, sort_keys=True)
        return web.Response(text=msg, content_type="application/manifest+json")


class ThemesView(HomeAssistantView):
    """View to return defined themes."""

    requires_auth = False
    url = '/api/themes'
    name = 'api:themes'

    @callback
    def get(self, request):
        """Return themes."""
        hass = request.app['hass']

        return self.json({
            'themes': hass.data[DATA_THEMES],
            'default_theme': hass.data[DATA_DEFAULT_THEME],
        })


def _fingerprint(path):
    """Fingerprint a file."""
    with open(path) as fil:
        return hashlib.md5(fil.read().encode('utf-8')).hexdigest()


def _is_latest(js_option, request):
    """
    Return whether we should serve latest untranspiled code.

    Set according to user's preference and URL override.
    """
    if request is None:
        return js_option == 'latest'

    # latest in query
    if 'latest' in request.query or (
            request.headers.get('Referer') and
            'latest' in urlparse(request.headers['Referer']).query):
        return True

    # es5 in query
    if 'es5' in request.query or (
            request.headers.get('Referer') and
            'es5' in urlparse(request.headers['Referer']).query):
        return False

    # non-auto option in config
    if js_option != 'auto':
        return js_option == 'latest'

    useragent = request.headers.get('User-Agent')
    if not useragent:
        return False

    from user_agents import parse
    useragent = parse(useragent)

    # on iOS every browser is a Safari which we support from version 11.
    if useragent.os.family == 'iOS':
        # Was >= 10, temp setting it to 12 to work around issue #11387
        return useragent.os.version[0] >= 12

    family_min_version = {
        'Chrome': 54,          # Object.values
        'Chrome Mobile': 54,
        'Firefox': 47,         # Object.values
        'Firefox Mobile': 47,
        'Opera': 41,           # Object.values
        'Edge': 14,            # Array.prototype.includes added in 14
        'Safari': 10,          # Many features not supported by 9
    }
    version = family_min_version.get(useragent.browser.family)
    return version and useragent.browser.version[0] >= version
