"""Register a custom front end panel."""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "panel_custom"
CONF_COMPONENT_NAME = "name"
CONF_SIDEBAR_TITLE = "sidebar_title"
CONF_SIDEBAR_ICON = "sidebar_icon"
CONF_URL_PATH = "url_path"
CONF_CONFIG = "config"
CONF_WEBCOMPONENT_PATH = "webcomponent_path"
CONF_JS_URL = "js_url"
CONF_MODULE_URL = "module_url"
CONF_EMBED_IFRAME = "embed_iframe"
CONF_TRUST_EXTERNAL_SCRIPT = "trust_external_script"
CONF_URL_EXCLUSIVE_GROUP = "url_exclusive_group"
CONF_REQUIRE_ADMIN = "require_admin"

DEFAULT_EMBED_IFRAME = False
DEFAULT_TRUST_EXTERNAL = False

DEFAULT_ICON = "mdi:bookmark"
LEGACY_URL = "/api/panel_custom/{}"

PANEL_DIR = "panels"


def url_validator(value):
    """Validate required urls are specified."""
    has_js_url = CONF_JS_URL in value
    has_html_url = CONF_WEBCOMPONENT_PATH in value
    has_module_url = CONF_MODULE_URL in value

    if has_html_url and (has_js_url or has_module_url):
        raise vol.Invalid("You cannot specify other urls besides a webcomponent path")

    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.All(
                    cv.deprecated(CONF_WEBCOMPONENT_PATH),
                    vol.Schema(
                        {
                            vol.Required(CONF_COMPONENT_NAME): cv.string,
                            vol.Optional(CONF_SIDEBAR_TITLE): cv.string,
                            vol.Optional(
                                CONF_SIDEBAR_ICON, default=DEFAULT_ICON
                            ): cv.icon,
                            vol.Optional(CONF_URL_PATH): cv.string,
                            vol.Optional(CONF_CONFIG): dict,
                            vol.Optional(
                                CONF_WEBCOMPONENT_PATH,
                            ): cv.string,
                            vol.Optional(
                                CONF_JS_URL,
                            ): cv.string,
                            vol.Optional(
                                CONF_MODULE_URL,
                            ): cv.string,
                            vol.Optional(
                                CONF_EMBED_IFRAME, default=DEFAULT_EMBED_IFRAME
                            ): cv.boolean,
                            vol.Optional(
                                CONF_TRUST_EXTERNAL_SCRIPT,
                                default=DEFAULT_TRUST_EXTERNAL,
                            ): cv.boolean,
                            vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
                        }
                    ),
                    url_validator,
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@bind_hass
async def async_register_panel(
    hass,
    # The url to serve the panel
    frontend_url_path,
    # The webcomponent name that loads your panel
    webcomponent_name,
    # Title/icon for sidebar
    sidebar_title=None,
    sidebar_icon=None,
    # HTML source of your panel
    html_url=None,
    # JS source of your panel
    js_url=None,
    # JS module of your panel
    module_url=None,
    # If your panel should be run inside an iframe
    embed_iframe=DEFAULT_EMBED_IFRAME,
    # Should user be asked for confirmation when loading external source
    trust_external=DEFAULT_TRUST_EXTERNAL,
    # Configuration to be passed to the panel
    config=None,
    # If your panel should only be shown to admin users
    require_admin=False,
):
    """Register a new custom panel."""
    if js_url is None and html_url is None and module_url is None:
        raise ValueError("Either js_url, module_url or html_url is required.")
    if html_url and (js_url or module_url):
        raise ValueError("You cannot specify other paths with an HTML url")
    if config is not None and not isinstance(config, dict):
        raise ValueError("Config needs to be a dictionary.")

    if html_url:
        _LOGGER.warning("HTML custom panels have been deprecated")

    custom_panel_config = {
        "name": webcomponent_name,
        "embed_iframe": embed_iframe,
        "trust_external": trust_external,
    }

    if js_url is not None:
        custom_panel_config["js_url"] = js_url

    if module_url is not None:
        custom_panel_config["module_url"] = module_url

    if html_url is not None:
        custom_panel_config["html_url"] = html_url

    if config is not None:
        # Make copy because we're mutating it
        config = dict(config)
    else:
        config = {}

    config["_panel_custom"] = custom_panel_config

    hass.components.frontend.async_register_built_in_panel(
        component_name="custom",
        sidebar_title=sidebar_title,
        sidebar_icon=sidebar_icon,
        frontend_url_path=frontend_url_path,
        config=config,
        require_admin=require_admin,
    )


async def async_setup(hass, config):
    """Initialize custom panel."""
    if DOMAIN not in config:
        return True

    seen = set()

    for panel in config[DOMAIN]:
        name = panel[CONF_COMPONENT_NAME]

        kwargs = {
            "webcomponent_name": panel[CONF_COMPONENT_NAME],
            "frontend_url_path": panel.get(CONF_URL_PATH, name),
            "sidebar_title": panel.get(CONF_SIDEBAR_TITLE),
            "sidebar_icon": panel.get(CONF_SIDEBAR_ICON),
            "config": panel.get(CONF_CONFIG),
            "trust_external": panel[CONF_TRUST_EXTERNAL_SCRIPT],
            "embed_iframe": panel[CONF_EMBED_IFRAME],
            "require_admin": panel[CONF_REQUIRE_ADMIN],
        }

        if CONF_JS_URL in panel:
            kwargs["js_url"] = panel[CONF_JS_URL]

        if CONF_MODULE_URL in panel:
            kwargs["module_url"] = panel[CONF_MODULE_URL]

        if CONF_MODULE_URL not in panel and CONF_JS_URL not in panel:
            if name in seen:
                _LOGGER.warning(
                    "Got HTML panel with duplicate name %s. Not registering", name
                )
                continue

            seen.add(name)
            panel_path = panel.get(CONF_WEBCOMPONENT_PATH)

            if panel_path is None:
                panel_path = hass.config.path(PANEL_DIR, f"{name}.html")

            if not await hass.async_add_executor_job(os.path.isfile, panel_path):
                _LOGGER.error(
                    "Unable to find webcomponent for %s: %s", name, panel_path
                )
                continue

            url = LEGACY_URL.format(name)
            hass.http.register_static_path(url, panel_path)
            kwargs["html_url"] = url

        try:
            await async_register_panel(hass, **kwargs)
        except ValueError as err:
            _LOGGER.error(
                "Unable to register panel %s: %s",
                panel.get(CONF_SIDEBAR_TITLE, name),
                err,
            )

    return True
