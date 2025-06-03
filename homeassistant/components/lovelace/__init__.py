"""Support for the Lovelace UI."""

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, onboarding, websocket_api
from homeassistant.config import (
    async_hass_config_yaml,
    async_process_component_and_handle_errors,
)
from homeassistant.const import CONF_FILENAME, CONF_MODE, CONF_RESOURCES
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import slugify

from . import dashboard, resources, websocket
from .const import (  # noqa: F401
    CONF_ALLOW_SINGLE_WORD,
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    DASHBOARD_BASE_CREATE_FIELDS,
    DEFAULT_ICON,
    DOMAIN,
    EVENT_LOVELACE_UPDATED,
    LOVELACE_DATA,
    MODE_STORAGE,
    MODE_YAML,
    RESOURCE_CREATE_FIELDS,
    RESOURCE_RELOAD_SERVICE_SCHEMA,
    RESOURCE_SCHEMA,
    RESOURCE_UPDATE_FIELDS,
    SERVICE_RELOAD_RESOURCES,
    STORAGE_DASHBOARD_CREATE_FIELDS,
    STORAGE_DASHBOARD_UPDATE_FIELDS,
)
from .system_health import system_health_info  # noqa: F401

_LOGGER = logging.getLogger(__name__)


def _validate_url_slug(value: Any) -> str:
    """Validate value is a valid url slug."""
    if value is None:
        raise vol.Invalid("Slug should not be None")
    if "-" not in value:
        raise vol.Invalid("Url path needs to contain a hyphen (-)")
    str_value = str(value)
    slg = slugify(str_value, separator="-")
    if str_value == slg:
        return str_value
    raise vol.Invalid(f"invalid slug {value} (try {slg})")


CONF_DASHBOARDS = "dashboards"

YAML_DASHBOARD_SCHEMA = vol.Schema(
    {
        **DASHBOARD_BASE_CREATE_FIELDS,
        vol.Required(CONF_MODE): MODE_YAML,
        vol.Required(CONF_FILENAME): cv.path,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default={}): vol.Schema(
            {
                vol.Optional(CONF_MODE, default=MODE_STORAGE): vol.All(
                    vol.Lower, vol.In([MODE_YAML, MODE_STORAGE])
                ),
                vol.Optional(CONF_DASHBOARDS): cv.schema_with_slug_keys(
                    YAML_DASHBOARD_SCHEMA,
                    slug_validator=_validate_url_slug,
                ),
                vol.Optional(CONF_RESOURCES): [RESOURCE_SCHEMA],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class LovelaceData:
    """Dataclass to store information in hass.data."""

    mode: str
    dashboards: dict[str | None, dashboard.LovelaceConfig]
    resources: resources.ResourceYAMLCollection | resources.ResourceStorageCollection
    yaml_dashboards: dict[str | None, ConfigType]

    def __getitem__(self, name: str) -> Any:
        """Enable method for compatibility reason.

        Following migration from an untyped dict to a dataclass in
        https://github.com/home-assistant/core/pull/136313
        """
        report_usage(
            f"accessed lovelace_data['{name}'] instead of lovelace_data.{name}",
            breaks_in_ha_version="2026.2",
            exclude_integrations={DOMAIN},
        )
        return getattr(self, name)

    def get(self, name: str, default: Any = None) -> Any:
        """Enable method for compatibility reason.

        Following migration from an untyped dict to a dataclass in
        https://github.com/home-assistant/core/pull/136313
        """
        report_usage(
            f"accessed lovelace_data.get('{name}') instead of lovelace_data.{name}",
            breaks_in_ha_version="2026.2",
            exclude_integrations={DOMAIN},
        )
        if hasattr(self, name):
            return getattr(self, name)
        return default


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Lovelace commands."""
    mode = config[DOMAIN][CONF_MODE]
    yaml_resources = config[DOMAIN].get(CONF_RESOURCES)

    frontend.async_register_built_in_panel(hass, DOMAIN, config={"mode": mode})

    async def reload_resources_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml resources."""
        try:
            conf = await async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        integration = await async_get_integration(hass, DOMAIN)

        config = await async_process_component_and_handle_errors(
            hass, conf, integration
        )

        if config is None:
            raise HomeAssistantError("Config validation failed")

        resource_collection = await create_yaml_resource_col(
            hass, config[DOMAIN].get(CONF_RESOURCES)
        )
        hass.data[LOVELACE_DATA].resources = resource_collection

    default_config: dashboard.LovelaceConfig
    resource_collection: (
        resources.ResourceYAMLCollection | resources.ResourceStorageCollection
    )
    if mode == MODE_YAML:
        default_config = dashboard.LovelaceYAML(hass, None, None)
        resource_collection = await create_yaml_resource_col(hass, yaml_resources)

        async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_RELOAD_RESOURCES,
            reload_resources_service_handler,
            schema=RESOURCE_RELOAD_SERVICE_SCHEMA,
        )
        # Register lovelace/resources for backwards compatibility, remove in
        # Home Assistant Core 2025.1
        for command in ("lovelace/resources", "lovelace/resources/list"):
            websocket_api.async_register_command(
                hass,
                command,
                websocket.websocket_lovelace_resources,
                websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
                    {"type": command},
                ),
            )

    else:
        default_config = dashboard.LovelaceStorage(hass, None)

        if yaml_resources is not None:
            _LOGGER.warning(
                "Lovelace is running in storage mode. Define resources via user"
                " interface"
            )

        resource_collection = resources.ResourceStorageCollection(hass, default_config)

        resources.ResourceStorageCollectionWebsocket(
            resource_collection,
            "lovelace/resources",
            "resource",
            RESOURCE_CREATE_FIELDS,
            RESOURCE_UPDATE_FIELDS,
        ).async_setup(hass)

    websocket_api.async_register_command(hass, websocket.websocket_lovelace_config)
    websocket_api.async_register_command(hass, websocket.websocket_lovelace_save_config)
    websocket_api.async_register_command(
        hass, websocket.websocket_lovelace_delete_config
    )

    hass.data[LOVELACE_DATA] = LovelaceData(
        mode=mode,
        # We store a dictionary mapping url_path: config. None is the default.
        dashboards={None: default_config},
        resources=resource_collection,
        yaml_dashboards=config[DOMAIN].get(CONF_DASHBOARDS, {}),
    )

    if hass.config.recovery_mode:
        return True

    async def storage_dashboard_changed(
        change_type: str, item_id: str, item: dict
    ) -> None:
        """Handle a storage dashboard change."""
        url_path = item[CONF_URL_PATH]

        if change_type == collection.CHANGE_REMOVED:
            frontend.async_remove_panel(hass, url_path)
            await hass.data[LOVELACE_DATA].dashboards.pop(url_path).async_delete()
            return

        if change_type == collection.CHANGE_ADDED:
            existing = hass.data[LOVELACE_DATA].dashboards.get(url_path)

            if existing:
                _LOGGER.warning(
                    "Cannot register panel at %s, it is already defined in %s",
                    url_path,
                    existing,
                )
                return

            hass.data[LOVELACE_DATA].dashboards[url_path] = dashboard.LovelaceStorage(
                hass, item
            )

            update = False
        else:
            hass.data[LOVELACE_DATA].dashboards[url_path].config = item
            update = True

        try:
            _register_panel(hass, url_path, MODE_STORAGE, item, update)
        except ValueError:
            _LOGGER.warning("Failed to %s panel %s from storage", change_type, url_path)

    # Process YAML dashboards
    for url_path, dashboard_conf in hass.data[LOVELACE_DATA].yaml_dashboards.items():
        # For now always mode=yaml
        lovelace_config = dashboard.LovelaceYAML(hass, url_path, dashboard_conf)
        hass.data[LOVELACE_DATA].dashboards[url_path] = lovelace_config

        try:
            _register_panel(hass, url_path, MODE_YAML, dashboard_conf, False)
        except ValueError:
            _LOGGER.warning("Panel url path %s is not unique", url_path)

    # Process storage dashboards
    dashboards_collection = dashboard.DashboardsCollection(hass)

    dashboards_collection.async_add_listener(storage_dashboard_changed)
    await dashboards_collection.async_load()

    dashboard.DashboardsCollectionWebSocket(
        dashboards_collection,
        "lovelace/dashboards",
        "dashboard",
        STORAGE_DASHBOARD_CREATE_FIELDS,
        STORAGE_DASHBOARD_UPDATE_FIELDS,
    ).async_setup(hass)

    def create_map_dashboard() -> None:
        """Create a map dashboard."""
        hass.async_create_task(_create_map_dashboard(hass, dashboards_collection))

    if not onboarding.async_is_onboarded(hass):
        onboarding.async_add_listener(hass, create_map_dashboard)

    return True


async def create_yaml_resource_col(
    hass: HomeAssistant, yaml_resources: list[ConfigType] | None
) -> resources.ResourceYAMLCollection:
    """Create yaml resources collection."""
    if yaml_resources is None:
        default_config = dashboard.LovelaceYAML(hass, None, None)
        try:
            ll_conf = await default_config.async_load(False)
        except HomeAssistantError:
            pass
        else:
            if CONF_RESOURCES in ll_conf:
                _LOGGER.warning(
                    "Resources need to be specified in your configuration.yaml. Please"
                    " see the docs"
                )
                yaml_resources = ll_conf[CONF_RESOURCES]

    return resources.ResourceYAMLCollection(yaml_resources or [])


@callback
def _register_panel(
    hass: HomeAssistant, url_path: str | None, mode: str, config: dict, update: bool
) -> None:
    """Register a panel."""
    kwargs = {
        "frontend_url_path": url_path,
        "require_admin": config[CONF_REQUIRE_ADMIN],
        "config": {"mode": mode},
        "update": update,
    }

    if config[CONF_SHOW_IN_SIDEBAR]:
        kwargs["sidebar_title"] = config[CONF_TITLE]
        kwargs["sidebar_icon"] = config.get(CONF_ICON, DEFAULT_ICON)

    frontend.async_register_built_in_panel(hass, DOMAIN, **kwargs)


async def _create_map_dashboard(
    hass: HomeAssistant, dashboards_collection: dashboard.DashboardsCollection
) -> None:
    """Create a map dashboard."""
    translations = await async_get_translations(
        hass, hass.config.language, "dashboard", {onboarding.DOMAIN}
    )
    title = translations["component.onboarding.dashboard.map.title"]

    await dashboards_collection.async_create_item(
        {
            CONF_ALLOW_SINGLE_WORD: True,
            CONF_ICON: "mdi:map",
            CONF_TITLE: title,
            CONF_URL_PATH: "map",
        }
    )

    map_store = hass.data[LOVELACE_DATA].dashboards["map"]
    await map_store.async_save({"strategy": {"type": "map"}})
