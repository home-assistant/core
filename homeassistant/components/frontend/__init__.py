"""Handle the frontend for Home Assistant."""
import json
import logging
import mimetypes
import os
import pathlib
from typing import Any, Dict, Optional, Set, Tuple

from aiohttp import hdrs, web, web_urldispatcher
import jinja2
import voluptuous as vol
from yarl import URL

from homeassistant.components import websocket_api
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.config import async_hass_config_yaml
from homeassistant.const import CONF_NAME, EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.helpers import service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.translation import async_get_translations
from homeassistant.loader import bind_hass

from .storage import async_setup_frontend_storage

# mypy: allow-untyped-defs, no-check-untyped-defs

# Fix mimetypes for borked Windows machines
# https://github.com/home-assistant/home-assistant-polymer/issues/3336
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")


DOMAIN = "frontend"
CONF_THEMES = "themes"
CONF_EXTRA_HTML_URL = "extra_html_url"
CONF_EXTRA_HTML_URL_ES5 = "extra_html_url_es5"
CONF_EXTRA_MODULE_URL = "extra_module_url"
CONF_EXTRA_JS_URL_ES5 = "extra_js_url_es5"
CONF_FRONTEND_REPO = "development_repo"
CONF_JS_VERSION = "javascript_version"
EVENT_PANELS_UPDATED = "panels_updated"

DEFAULT_THEME_COLOR = "#03A9F4"

MANIFEST_JSON = {
    "background_color": "#FFFFFF",
    "description": "Home automation platform that puts local control and privacy first.",
    "dir": "ltr",
    "display": "standalone",
    "icons": [
        {
            "src": f"/static/icons/favicon-{size}x{size}.png",
            "sizes": f"{size}x{size}",
            "type": "image/png",
            "purpose": "maskable any",
        }
        for size in (192, 384, 512, 1024)
    ],
    "lang": "en-US",
    "name": "Home Assistant",
    "short_name": "Assistant",
    "start_url": "/?homescreen=1",
    "theme_color": DEFAULT_THEME_COLOR,
    "prefer_related_applications": True,
    "related_applications": [
        {"platform": "play", "id": "io.homeassistant.companion.android"}
    ],
}

DATA_PANELS = "frontend_panels"
DATA_JS_VERSION = "frontend_js_version"
DATA_EXTRA_HTML_URL = "frontend_extra_html_url"
DATA_EXTRA_HTML_URL_ES5 = "frontend_extra_html_url_es5"
DATA_EXTRA_MODULE_URL = "frontend_extra_module_url"
DATA_EXTRA_JS_URL_ES5 = "frontend_extra_js_url_es5"
DATA_THEMES = "frontend_themes"
DATA_DEFAULT_THEME = "frontend_default_theme"
DEFAULT_THEME = "default"

PRIMARY_COLOR = "primary-color"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_FRONTEND_REPO): cv.isdir,
                vol.Optional(CONF_THEMES): vol.Schema(
                    {cv.string: {cv.string: cv.string}}
                ),
                vol.Optional(CONF_EXTRA_HTML_URL): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_EXTRA_MODULE_URL): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_EXTRA_JS_URL_ES5): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                # We no longer use these options.
                vol.Optional(CONF_EXTRA_HTML_URL_ES5): cv.match_all,
                vol.Optional(CONF_JS_VERSION): cv.match_all,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_THEME = "set_theme"
SERVICE_RELOAD_THEMES = "reload_themes"


class Panel:
    """Abstract class for panels."""

    # Name of the webcomponent
    component_name: Optional[str] = None

    # Icon to show in the sidebar
    sidebar_icon: Optional[str] = None

    # Title to show in the sidebar
    sidebar_title: Optional[str] = None

    # Url to show the panel in the frontend
    frontend_url_path: Optional[str] = None

    # Config to pass to the webcomponent
    config: Optional[Dict[str, Any]] = None

    # If the panel should only be visible to admins
    require_admin = False

    def __init__(
        self,
        component_name,
        sidebar_title,
        sidebar_icon,
        frontend_url_path,
        config,
        require_admin,
    ):
        """Initialize a built-in panel."""
        self.component_name = component_name
        self.sidebar_title = sidebar_title
        self.sidebar_icon = sidebar_icon
        self.frontend_url_path = frontend_url_path or component_name
        self.config = config
        self.require_admin = require_admin

    @callback
    def to_response(self):
        """Panel as dictionary."""
        return {
            "component_name": self.component_name,
            "icon": self.sidebar_icon,
            "title": self.sidebar_title,
            "config": self.config,
            "url_path": self.frontend_url_path,
            "require_admin": self.require_admin,
        }


@bind_hass
@callback
def async_register_built_in_panel(
    hass,
    component_name,
    sidebar_title=None,
    sidebar_icon=None,
    frontend_url_path=None,
    config=None,
    require_admin=False,
    *,
    update=False,
):
    """Register a built-in panel."""
    panel = Panel(
        component_name,
        sidebar_title,
        sidebar_icon,
        frontend_url_path,
        config,
        require_admin,
    )

    panels = hass.data.setdefault(DATA_PANELS, {})

    if not update and panel.frontend_url_path in panels:
        raise ValueError(f"Overwriting panel {panel.frontend_url_path}")

    panels[panel.frontend_url_path] = panel

    hass.bus.async_fire(EVENT_PANELS_UPDATED)


@bind_hass
@callback
def async_remove_panel(hass, frontend_url_path):
    """Remove a built-in panel."""
    panel = hass.data.get(DATA_PANELS, {}).pop(frontend_url_path, None)

    if panel is None:
        _LOGGER.warning("Removing unknown panel %s", frontend_url_path)

    hass.bus.async_fire(EVENT_PANELS_UPDATED)


@bind_hass
@callback
def add_extra_html_url(hass, url, es5=False):
    """Register extra html url to load."""
    key = DATA_EXTRA_HTML_URL_ES5 if es5 else DATA_EXTRA_HTML_URL
    url_set = hass.data.get(key)
    if url_set is None:
        url_set = hass.data[key] = set()
    url_set.add(url)


def add_extra_js_url(hass, url, es5=False):
    """Register extra js or module url to load."""
    key = DATA_EXTRA_JS_URL_ES5 if es5 else DATA_EXTRA_MODULE_URL
    url_set = hass.data.get(key)
    if url_set is None:
        url_set = hass.data[key] = set()
    url_set.add(url)


def add_manifest_json_key(key, val):
    """Add a keyval to the manifest.json."""
    MANIFEST_JSON[key] = val


def _frontend_root(dev_repo_path):
    """Return root path to the frontend files."""
    if dev_repo_path is not None:
        return pathlib.Path(dev_repo_path) / "hass_frontend"
    # Keep import here so that we can import frontend without installing reqs
    # pylint: disable=import-outside-toplevel
    import hass_frontend

    return hass_frontend.where()


async def async_setup(hass, config):
    """Set up the serving of the frontend."""
    await async_setup_frontend_storage(hass)
    hass.components.websocket_api.async_register_command(websocket_get_panels)
    hass.components.websocket_api.async_register_command(websocket_get_themes)
    hass.components.websocket_api.async_register_command(websocket_get_translations)
    hass.http.register_view(ManifestJSONView)

    conf = config.get(DOMAIN, {})

    repo_path = conf.get(CONF_FRONTEND_REPO)
    is_dev = repo_path is not None
    root_path = _frontend_root(repo_path)

    for path, should_cache in (
        ("service_worker.js", False),
        ("robots.txt", False),
        ("onboarding.html", True),
        ("static", True),
        ("frontend_latest", True),
        ("frontend_es5", True),
    ):
        hass.http.register_static_path(f"/{path}", str(root_path / path), should_cache)

    hass.http.register_static_path(
        "/auth/authorize", str(root_path / "authorize.html"), False
    )

    local = hass.config.path("www")
    if os.path.isdir(local):
        hass.http.register_static_path("/local", local, not is_dev)

    hass.http.app.router.register_resource(IndexView(repo_path, hass))

    async_register_built_in_panel(hass, "profile")

    # To smooth transition to new urls, add redirects to new urls of dev tools
    # Added June 27, 2019. Can be removed in 2021.
    for panel in ("event", "info", "service", "state", "template", "mqtt"):
        hass.http.register_redirect(f"/dev-{panel}", f"/developer-tools/{panel}")

    async_register_built_in_panel(
        hass,
        "developer-tools",
        require_admin=True,
        sidebar_title="developer_tools",
        sidebar_icon="hass:hammer",
    )

    if DATA_EXTRA_HTML_URL not in hass.data:
        hass.data[DATA_EXTRA_HTML_URL] = set()

    for url in conf.get(CONF_EXTRA_HTML_URL, []):
        add_extra_html_url(hass, url, False)

    if DATA_EXTRA_MODULE_URL not in hass.data:
        hass.data[DATA_EXTRA_MODULE_URL] = set()

    for url in conf.get(CONF_EXTRA_MODULE_URL, []):
        add_extra_js_url(hass, url)

    if DATA_EXTRA_JS_URL_ES5 not in hass.data:
        hass.data[DATA_EXTRA_JS_URL_ES5] = set()

    for url in conf.get(CONF_EXTRA_JS_URL_ES5, []):
        add_extra_js_url(hass, url, True)

    _async_setup_themes(hass, conf.get(CONF_THEMES))

    return True


@callback
def _async_setup_themes(hass, themes):
    """Set up themes data and services."""
    hass.data[DATA_DEFAULT_THEME] = DEFAULT_THEME
    hass.data[DATA_THEMES] = themes or {}

    @callback
    def update_theme_and_fire_event():
        """Update theme_color in manifest."""
        name = hass.data[DATA_DEFAULT_THEME]
        themes = hass.data[DATA_THEMES]
        MANIFEST_JSON["theme_color"] = DEFAULT_THEME_COLOR
        if name != DEFAULT_THEME:
            MANIFEST_JSON["theme_color"] = themes[name].get(
                "app-header-background-color",
                themes[name].get(PRIMARY_COLOR, DEFAULT_THEME_COLOR),
            )
        hass.bus.async_fire(EVENT_THEMES_UPDATED)

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

    async def reload_themes(_):
        """Reload themes."""
        config = await async_hass_config_yaml(hass)
        new_themes = config[DOMAIN].get(CONF_THEMES, {})
        hass.data[DATA_THEMES] = new_themes
        if hass.data[DATA_DEFAULT_THEME] not in new_themes:
            hass.data[DATA_DEFAULT_THEME] = DEFAULT_THEME
        update_theme_and_fire_event()

    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_THEME,
        set_theme,
        vol.Schema({vol.Required(CONF_NAME): cv.string}),
    )

    service.async_register_admin_service(
        hass, DOMAIN, SERVICE_RELOAD_THEMES, reload_themes
    )


class IndexView(web_urldispatcher.AbstractResource):
    """Serve the frontend."""

    def __init__(self, repo_path, hass):
        """Initialize the frontend view."""
        super().__init__(name="frontend:index")
        self.repo_path = repo_path
        self.hass = hass
        self._template_cache = None

    @property
    def canonical(self) -> str:
        """Return resource's canonical path."""
        return "/"

    @property
    def _route(self):
        """Return the index route."""
        return web_urldispatcher.ResourceRoute("GET", self.get, self)

    def url_for(self, **kwargs: str) -> URL:
        """Construct url for resource with additional params."""
        return URL("/")

    async def resolve(
        self, request: web.Request
    ) -> Tuple[Optional[web_urldispatcher.UrlMappingMatchInfo], Set[str]]:
        """Resolve resource.

        Return (UrlMappingMatchInfo, allowed_methods) pair.
        """
        if (
            request.path != "/"
            and request.url.parts[1] not in self.hass.data[DATA_PANELS]
        ):
            return None, set()

        if request.method != hdrs.METH_GET:
            return None, {"GET"}

        return web_urldispatcher.UrlMappingMatchInfo({}, self._route), {"GET"}

    def add_prefix(self, prefix: str) -> None:
        """Add a prefix to processed URLs.

        Required for subapplications support.
        """

    def get_info(self):
        """Return a dict with additional info useful for introspection."""
        return {"panels": list(self.hass.data[DATA_PANELS])}

    def freeze(self) -> None:
        """Freeze the resource."""

    def raw_match(self, path: str) -> bool:
        """Perform a raw match against path."""

    def get_template(self):
        """Get template."""
        tpl = self._template_cache
        if tpl is None:
            with open(str(_frontend_root(self.repo_path) / "index.html")) as file:
                tpl = jinja2.Template(file.read())

            # Cache template if not running from repository
            if self.repo_path is None:
                self._template_cache = tpl

        return tpl

    async def get(self, request: web.Request) -> web.Response:
        """Serve the index page for panel pages."""
        hass = request.app["hass"]

        if not hass.components.onboarding.async_is_onboarded():
            return web.Response(status=302, headers={"location": "/onboarding.html"})

        template = self._template_cache

        if template is None:
            template = await hass.async_add_executor_job(self.get_template)

        return web.Response(
            text=template.render(
                theme_color=MANIFEST_JSON["theme_color"],
                extra_urls=hass.data[DATA_EXTRA_HTML_URL],
                extra_modules=hass.data[DATA_EXTRA_MODULE_URL],
                extra_js_es5=hass.data[DATA_EXTRA_JS_URL_ES5],
            ),
            content_type="text/html",
        )

    def __len__(self) -> int:
        """Return length of resource."""
        return 1

    def __iter__(self):
        """Iterate over routes."""
        return iter([self._route])


class ManifestJSONView(HomeAssistantView):
    """View to return a manifest.json."""

    requires_auth = False
    url = "/manifest.json"
    name = "manifestjson"

    @callback
    def get(self, request):  # pylint: disable=no-self-use
        """Return the manifest.json."""
        msg = json.dumps(MANIFEST_JSON, sort_keys=True)
        return web.Response(text=msg, content_type="application/manifest+json")


@callback
@websocket_api.websocket_command({"type": "get_panels"})
def websocket_get_panels(hass, connection, msg):
    """Handle get panels command.

    Async friendly.
    """
    user_is_admin = connection.user.is_admin
    panels = {
        panel_key: panel.to_response()
        for panel_key, panel in connection.hass.data[DATA_PANELS].items()
        if user_is_admin or not panel.require_admin
    }

    connection.send_message(websocket_api.result_message(msg["id"], panels))


@callback
@websocket_api.websocket_command({"type": "frontend/get_themes"})
def websocket_get_themes(hass, connection, msg):
    """Handle get themes command.

    Async friendly.
    """
    if hass.config.safe_mode:
        connection.send_message(
            websocket_api.result_message(
                msg["id"],
                {
                    "themes": {
                        "safe_mode": {
                            "primary-color": "#db4437",
                            "accent-color": "#eeee02",
                        }
                    },
                    "default_theme": "safe_mode",
                },
            )
        )
        return

    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "themes": hass.data[DATA_THEMES],
                "default_theme": hass.data[DATA_DEFAULT_THEME],
            },
        )
    )


@websocket_api.websocket_command(
    {
        "type": "frontend/get_translations",
        vol.Required("language"): str,
        vol.Required("category"): str,
        vol.Optional("integration"): str,
        vol.Optional("config_flow"): bool,
    }
)
@websocket_api.async_response
async def websocket_get_translations(hass, connection, msg):
    """Handle get translations command.

    Async friendly.
    """
    resources = await async_get_translations(
        hass,
        msg["language"],
        msg["category"],
        msg.get("integration"),
        msg.get("config_flow"),
    )
    connection.send_message(
        websocket_api.result_message(msg["id"], {"resources": resources})
    )
