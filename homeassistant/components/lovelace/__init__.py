"""Support for the Lovelace UI."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.const import CONF_FILENAME, CONF_ICON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.util import sanitize_filename, slugify

from . import dashboard, resources, websocket
from .const import (
    CONF_RESOURCES,
    DOMAIN,
    LOVELACE_CONFIG_FILE,
    MODE_STORAGE,
    MODE_YAML,
    RESOURCE_CREATE_FIELDS,
    RESOURCE_SCHEMA,
    RESOURCE_UPDATE_FIELDS,
)

_LOGGER = logging.getLogger(__name__)

CONF_MODE = "mode"

CONF_DASHBOARDS = "dashboards"
CONF_SIDEBAR = "sidebar"
CONF_TITLE = "title"
CONF_REQUIRE_ADMIN = "require_admin"

DASHBOARD_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
        vol.Optional(CONF_SIDEBAR): {
            vol.Required(CONF_ICON): cv.icon,
            vol.Required(CONF_TITLE): cv.string,
        },
    }
)

YAML_DASHBOARD_SCHEMA = DASHBOARD_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_MODE): MODE_YAML,
        vol.Required(CONF_FILENAME): vol.All(cv.string, sanitize_filename),
    }
)


def url_slug(value: Any) -> str:
    """Validate value is a valid url slug."""
    if value is None:
        raise vol.Invalid("Slug should not be None")
    str_value = str(value)
    slg = slugify(str_value, separator="-")
    if str_value == slg:
        return str_value
    raise vol.Invalid(f"invalid slug {value} (try {slg})")


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default={}): vol.Schema(
            {
                vol.Optional(CONF_MODE, default=MODE_STORAGE): vol.All(
                    vol.Lower, vol.In([MODE_YAML, MODE_STORAGE])
                ),
                vol.Optional(CONF_DASHBOARDS): cv.schema_with_slug_keys(
                    YAML_DASHBOARD_SCHEMA, slug_validator=url_slug,
                ),
                vol.Optional(CONF_RESOURCES): [RESOURCE_SCHEMA],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Pass in default to `get` because defaults not set if loaded as dep
    mode = config[DOMAIN][CONF_MODE]
    yaml_resources = config[DOMAIN].get(CONF_RESOURCES)

    frontend.async_register_built_in_panel(hass, DOMAIN, config={"mode": mode})

    if mode == MODE_YAML:
        default_config = dashboard.LovelaceYAML(hass, None, LOVELACE_CONFIG_FILE)

        if yaml_resources is None:
            try:
                ll_conf = await default_config.async_load(False)
            except HomeAssistantError:
                pass
            else:
                if CONF_RESOURCES in ll_conf:
                    _LOGGER.warning(
                        "Resources need to be specified in your configuration.yaml. Please see the docs."
                    )
                    yaml_resources = ll_conf[CONF_RESOURCES]

        resource_collection = resources.ResourceYAMLCollection(yaml_resources or [])

    else:
        default_config = dashboard.LovelaceStorage(hass, None)

        if yaml_resources is not None:
            _LOGGER.warning(
                "Lovelace is running in storage mode. Define resources via user interface"
            )

        resource_collection = resources.ResourceStorageCollection(hass, default_config)

        collection.StorageCollectionWebsocket(
            resource_collection,
            "lovelace/resources",
            "resource",
            RESOURCE_CREATE_FIELDS,
            RESOURCE_UPDATE_FIELDS,
        ).async_setup(hass, create_list=False)

    hass.components.websocket_api.async_register_command(
        websocket.websocket_lovelace_config
    )
    hass.components.websocket_api.async_register_command(
        websocket.websocket_lovelace_save_config
    )
    hass.components.websocket_api.async_register_command(
        websocket.websocket_lovelace_delete_config
    )
    hass.components.websocket_api.async_register_command(
        websocket.websocket_lovelace_resources
    )

    hass.components.system_health.async_register_info(DOMAIN, system_health_info)

    hass.data[DOMAIN] = {
        # We store a dictionary mapping url_path: config. None is the default.
        "dashboards": {None: default_config},
        "resources": resource_collection,
    }

    if hass.config.safe_mode or CONF_DASHBOARDS not in config[DOMAIN]:
        return True

    for url_path, dashboard_conf in config[DOMAIN][CONF_DASHBOARDS].items():
        # For now always mode=yaml
        config = dashboard.LovelaceYAML(hass, url_path, dashboard_conf[CONF_FILENAME])
        hass.data[DOMAIN]["dashboards"][url_path] = config

        kwargs = {
            "hass": hass,
            "component_name": DOMAIN,
            "frontend_url_path": url_path,
            "require_admin": dashboard_conf[CONF_REQUIRE_ADMIN],
            "config": {"mode": dashboard_conf[CONF_MODE]},
        }

        if CONF_SIDEBAR in dashboard_conf:
            kwargs["sidebar_title"] = dashboard_conf[CONF_SIDEBAR][CONF_TITLE]
            kwargs["sidebar_icon"] = dashboard_conf[CONF_SIDEBAR][CONF_ICON]

        try:
            frontend.async_register_built_in_panel(**kwargs)
        except ValueError:
            _LOGGER.warning("Panel url path %s is not unique", url_path)

    return True


async def system_health_info(hass):
    """Get info for the info page."""
    return await hass.data[DOMAIN]["dashboards"][None].async_get_info()
