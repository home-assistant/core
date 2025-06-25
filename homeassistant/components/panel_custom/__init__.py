"""Register a custom front end panel."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "panel_custom"
CONF_COMPONENT_NAME = "name"
CONF_SIDEBAR_TITLE = "sidebar_title"
CONF_SIDEBAR_ICON = "sidebar_icon"
CONF_URL_PATH = "url_path"
CONF_CONFIG = "config"
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


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_COMPONENT_NAME): cv.string,
                        vol.Optional(CONF_SIDEBAR_TITLE): cv.string,
                        vol.Optional(CONF_SIDEBAR_ICON, default=DEFAULT_ICON): cv.icon,
                        vol.Optional(CONF_URL_PATH): cv.string,
                        vol.Optional(CONF_CONFIG): dict,
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
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@bind_hass
async def async_register_panel(
    hass: HomeAssistant,
    # The url to serve the panel
    frontend_url_path: str,
    # The webcomponent name that loads your panel
    webcomponent_name: str,
    # Title/icon for sidebar
    sidebar_title: str | None = None,
    sidebar_icon: str | None = None,
    # JS source of your panel
    js_url: str | None = None,
    # JS module of your panel
    module_url: str | None = None,
    # If your panel should be run inside an iframe
    embed_iframe: bool = DEFAULT_EMBED_IFRAME,
    # Should user be asked for confirmation when loading external source
    trust_external: bool = DEFAULT_TRUST_EXTERNAL,
    # Configuration to be passed to the panel
    config: ConfigType | None = None,
    # If your panel should only be shown to admin users
    require_admin: bool = False,
    # If your panel is used to configure an integration, needs the domain of the integration
    config_panel_domain: str | None = None,
) -> None:
    """Register a new custom panel."""
    if js_url is None and module_url is None:
        raise ValueError("Either js_url, module_url or html_url is required.")
    if config is not None and not isinstance(config, dict):
        raise ValueError("Config needs to be a dictionary.")

    custom_panel_config = {
        "name": webcomponent_name,
        "embed_iframe": embed_iframe,
        "trust_external": trust_external,
    }

    if js_url is not None:
        custom_panel_config["js_url"] = js_url

    if module_url is not None:
        custom_panel_config["module_url"] = module_url

    if config is not None:
        # Make copy because we're mutating it
        config = dict(config)
    else:
        config = {}

    config["_panel_custom"] = custom_panel_config

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=sidebar_title,
        sidebar_icon=sidebar_icon,
        frontend_url_path=frontend_url_path,
        config=config,
        require_admin=require_admin,
        config_panel_domain=config_panel_domain,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize custom panel."""
    if DOMAIN not in config:
        return True

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

        try:
            await async_register_panel(hass, **kwargs)
        except ValueError as err:
            _LOGGER.error(
                "Unable to register panel %s: %s",
                panel.get(CONF_SIDEBAR_TITLE, name),
                err,
            )

    return True
