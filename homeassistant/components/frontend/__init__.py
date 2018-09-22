"""
Handle the frontend for Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/frontend/
"""
import asyncio
import json
import logging
import os
from urllib.parse import urlparse

from aiohttp import web
import voluptuous as vol
import jinja2

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.components import websocket_api
from homeassistant.config import find_config_file, load_yaml_config_file
from homeassistant.const import CONF_NAME, EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.loader import bind_hass
from homeassistant.util.yaml import load_yaml

REQUIREMENTS = ['ais-dom-frontend==20180920.0']

DOMAIN = 'frontend'
DEPENDENCIES = ['api', 'websocket_api', 'http', 'system_log',
                'auth', 'onboarding']

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
    'start_url': '/?homescreen=1',
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
WS_TYPE_GET_PANELS = 'get_panels'
SCHEMA_GET_PANELS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_PANELS,
})
WS_TYPE_GET_THEMES = 'frontend/get_themes'
SCHEMA_GET_THEMES = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_THEMES,
})
WS_TYPE_GET_TRANSLATIONS = 'frontend/get_translations'
SCHEMA_GET_TRANSLATIONS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_TRANSLATIONS,
    vol.Required('language'): str,
})
WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_LOVELACE_UI,
})


class Panel:
    """Abstract class for panels."""

    # Name of the webcomponent
    component_name = None

    # Icon to show in the sidebar (optional)
    sidebar_icon = None

    # Title to show in the sidebar (optional)
    sidebar_title = None

    # Url to show the panel in the frontend
    frontend_url_path = None

    # Config to pass to the webcomponent
    config = None

    def __init__(self, component_name, sidebar_title, sidebar_icon,
                 frontend_url_path, config):
        """Initialize a built-in panel."""
        self.component_name = component_name
        self.sidebar_title = sidebar_title
        self.sidebar_icon = sidebar_icon
        self.frontend_url_path = frontend_url_path or component_name
        self.config = config

    @callback
    def async_register_index_routes(self, router, index_view):
        """Register routes for panel to be served by index view."""
        router.add_route(
            'get', '/{}'.format(self.frontend_url_path), index_view.get)
        router.add_route(
            'get', '/{}/{{extra:.+}}'.format(self.frontend_url_path),
            index_view.get)

    @callback
    def to_response(self, hass, request):
        """Panel as dictionary."""
        return {
            'component_name': self.component_name,
            'icon': self.sidebar_icon,
            'title': self.sidebar_title,
            'config': self.config,
            'url_path': self.frontend_url_path,
        }


@bind_hass
async def async_register_built_in_panel(hass, component_name,
                                        sidebar_title=None, sidebar_icon=None,
                                        frontend_url_path=None, config=None):
    """Register a built-in panel."""
    panel = Panel(component_name, sidebar_title, sidebar_icon,
                  frontend_url_path, config)

    panels = hass.data.get(DATA_PANELS)
    if panels is None:
        panels = hass.data[DATA_PANELS] = {}

    if panel.frontend_url_path in panels:
        _LOGGER.warning("Overwriting component %s", panel.frontend_url_path)

    if DATA_FINALIZE_PANEL in hass.data:
        hass.data[DATA_FINALIZE_PANEL](panel)

    panels[panel.frontend_url_path] = panel


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


async def async_setup(hass, config):
    """Set up the serving of the frontend."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_PANELS, websocket_get_panels, SCHEMA_GET_PANELS)
    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_THEMES, websocket_get_themes, SCHEMA_GET_THEMES)
    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_TRANSLATIONS, websocket_get_translations,
        SCHEMA_GET_TRANSLATIONS)
    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)
    hass.http.register_view(ManifestJSONView)

    conf = config.get(DOMAIN, {})

    repo_path = conf.get(CONF_FRONTEND_REPO)
    is_dev = repo_path is not None
    hass.data[DATA_JS_VERSION] = js_version = conf.get(CONF_JS_VERSION)

    if is_dev:
        hass_frontend_path = os.path.join(repo_path, 'hass_frontend')
        hass_frontend_es5_path = os.path.join(repo_path, 'hass_frontend_es5')
    else:
        import hass_frontend
        import hass_frontend_es5
        hass_frontend_path = hass_frontend.where()
        hass_frontend_es5_path = hass_frontend_es5.where()

    hass.http.register_static_path(
        "/service_worker_es5.js",
        os.path.join(hass_frontend_es5_path, "service_worker.js"), False)
    hass.http.register_static_path(
        "/service_worker.js",
        os.path.join(hass_frontend_path, "service_worker.js"), False)
    hass.http.register_static_path(
        "/robots.txt",
        os.path.join(hass_frontend_path, "robots.txt"), False)
    hass.http.register_static_path("/static", hass_frontend_path, not is_dev)
    hass.http.register_static_path(
        "/frontend_latest", hass_frontend_path, not is_dev)
    hass.http.register_static_path(
        "/frontend_es5", hass_frontend_es5_path, not is_dev)

    local = hass.config.path('www')
    if os.path.isdir(local):
        hass.http.register_static_path("/local", local, not is_dev)

    index_view = IndexView(repo_path, js_version, hass.auth.active)
    hass.http.register_view(index_view)
    hass.http.register_view(AuthorizeView(repo_path, js_version))

    @callback
    def async_finalize_panel(panel):
        """Finalize setup of a panel."""
        panel.async_register_index_routes(hass.http.app.router, index_view)

    await asyncio.wait(
        [async_register_built_in_panel(hass, panel) for panel in (
            'dev-event', 'dev-info', 'dev-service', 'dev-state',
            'dev-template', 'dev-mqtt', 'kiosk', 'lovelace', 'profile')],
        loop=hass.loop)

    hass.data[DATA_FINALIZE_PANEL] = async_finalize_panel

    # Finalize registration of panels that registered before frontend was setup
    # This includes the built-in panels from line above.
    for panel in hass.data[DATA_PANELS].values():
        async_finalize_panel(panel)

    if DATA_EXTRA_HTML_URL not in hass.data:
        hass.data[DATA_EXTRA_HTML_URL] = set()
    if DATA_EXTRA_HTML_URL_ES5 not in hass.data:
        hass.data[DATA_EXTRA_HTML_URL_ES5] = set()

    for url in conf.get(CONF_EXTRA_HTML_URL, []):
        add_extra_html_url(hass, url, False)
    for url in conf.get(CONF_EXTRA_HTML_URL_ES5, []):
        add_extra_html_url(hass, url, True)

    _async_setup_themes(hass, conf.get(CONF_THEMES))

    return True


@callback
def _async_setup_themes(hass, themes):
    """Set up themes data and services."""
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


class AuthorizeView(HomeAssistantView):
    """Serve the frontend."""

    url = '/auth/authorize'
    name = 'auth:authorize'
    requires_auth = False

    def __init__(self, repo_path, js_option):
        """Initialize the frontend view."""
        self.repo_path = repo_path
        self.js_option = js_option

    async def get(self, request: web.Request):
        """Redirect to the authorize page."""
        latest = self.repo_path is not None or \
            _is_latest(self.js_option, request)

        if latest:
            location = '/frontend_latest/authorize.html'
        else:
            location = '/frontend_es5/authorize.html'

        location += '?{}'.format(request.query_string)

        return web.Response(status=302, headers={
            'location': location
        })


class IndexView(HomeAssistantView):
    """Serve the frontend."""

    url = '/'
    name = 'frontend:index'
    requires_auth = False
    extra_urls = ['/states', '/states/{extra}']

    def __init__(self, repo_path, js_option, auth_active):
        """Initialize the frontend view."""
        self.repo_path = repo_path
        self.js_option = js_option
        self.auth_active = auth_active
        self._template_cache = {}

    def get_template(self, latest):
        """Get template."""
        if self.repo_path is not None:
            root = os.path.join(self.repo_path, 'hass_frontend')
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

    async def get(self, request, extra=None):
        """Serve the index view."""
        hass = request.app['hass']
        latest = self.repo_path is not None or \
            _is_latest(self.js_option, request)

        if not hass.components.onboarding.async_is_onboarded():
            if latest:
                location = '/frontend_latest/onboarding.html'
            else:
                location = '/frontend_es5/onboarding.html'

            return web.Response(status=302, headers={
                'location': location
            })

        no_auth = '1'
        if hass.config.api.api_password and not request[KEY_AUTHENTICATED]:
            # do not try to auto connect on load
            no_auth = '0'

        use_oauth = '1' if self.auth_active else '0'

        template = await hass.async_add_job(self.get_template, latest)

        extra_key = DATA_EXTRA_HTML_URL if latest else DATA_EXTRA_HTML_URL_ES5

        template_params = dict(
            no_auth=no_auth,
            theme_color=MANIFEST_JSON['theme_color'],
            extra_urls=hass.data[extra_key],
            use_oauth=use_oauth
        )

        return web.Response(text=template.render(**template_params),
                            content_type='text/html')


class ManifestJSONView(HomeAssistantView):
    """View to return a manifest.json."""

    requires_auth = False
    url = '/manifest.json'
    name = 'manifestjson'

    @callback
    def get(self, request):    # pylint: disable=no-self-use
        """Return the manifest.json."""
        msg = json.dumps(MANIFEST_JSON, sort_keys=True)
        return web.Response(text=msg, content_type="application/manifest+json")


def _is_latest(js_option, request):
    """
    Return whether we should serve latest untranspiled code.

    Set according to user's preference and URL override.
    """
    import hass_frontend

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

    return useragent and hass_frontend.version(useragent)


@callback
def websocket_get_panels(hass, connection, msg):
    """Handle get panels command.

    Async friendly.
    """
    panels = {
        panel:
        connection.hass.data[DATA_PANELS][panel].to_response(
            connection.hass, connection.request)
        for panel in connection.hass.data[DATA_PANELS]}

    connection.to_write.put_nowait(websocket_api.result_message(
        msg['id'], panels))


@callback
def websocket_get_themes(hass, connection, msg):
    """Handle get themes command.

    Async friendly.
    """
    connection.to_write.put_nowait(websocket_api.result_message(msg['id'], {
        'themes': hass.data[DATA_THEMES],
        'default_theme': hass.data[DATA_DEFAULT_THEME],
    }))


@callback
def websocket_get_translations(hass, connection, msg):
    """Handle get translations command.

    Async friendly.
    """
    async def send_translations():
        """Send a translation."""
        resources = await async_get_translations(hass, msg['language'])
        connection.send_message_outside(websocket_api.result_message(
            msg['id'], {
                'resources': resources,
            }
        ))

    hass.async_add_job(send_translations())


def websocket_lovelace_config(hass, connection, msg):
    """Send lovelace UI config over websocket config."""
    async def send_exp_config():
        """Send lovelace frontend config."""
        error = None
        try:
            config = await hass.async_add_job(
                load_yaml, hass.config.path('ui-lovelace.yaml'))
            message = websocket_api.result_message(
                msg['id'], config
            )
        except FileNotFoundError:
            error = ('file_not_found',
                     'Could not find ui-lovelace.yaml in your config dir.')
        except HomeAssistantError as err:
            error = 'load_error', str(err)

        if error is not None:
            message = websocket_api.error_message(msg['id'], *error)

        connection.send_message_outside(message)

    hass.async_add_job(send_exp_config())
