"""Insteon API interface for the frontend."""

from insteon_frontend import get_build_id, locate_dir

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from ..const import CONF_DEV_PATH, DOMAIN
from .aldb import (
    websocket_add_default_links,
    websocket_change_aldb_record,
    websocket_create_aldb_record,
    websocket_get_aldb,
    websocket_load_aldb,
    websocket_notify_on_aldb_status,
    websocket_notify_on_aldb_status_all,
    websocket_reset_aldb,
    websocket_write_aldb,
)
from .config import (
    websocket_add_device_override,
    websocket_get_broken_links,
    websocket_get_config,
    websocket_get_modem_schema,
    websocket_get_unknown_devices,
    websocket_remove_device_override,
    websocket_update_modem_config,
)
from .device import (
    websocket_add_device,
    websocket_add_x10_device,
    websocket_cancel_add_device,
    websocket_get_device,
    websocket_remove_device,
)
from .properties import (
    websocket_change_properties_record,
    websocket_get_properties,
    websocket_load_properties,
    websocket_reset_properties,
    websocket_write_properties,
)
from .scenes import (
    websocket_delete_scene,
    websocket_get_scene,
    websocket_get_scenes,
    websocket_save_scene,
)

URL_BASE = "/insteon_static"


@callback
def async_load_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_device)
    websocket_api.async_register_command(hass, websocket_add_device)
    websocket_api.async_register_command(hass, websocket_cancel_add_device)

    websocket_api.async_register_command(hass, websocket_get_scenes)
    websocket_api.async_register_command(hass, websocket_get_scene)
    websocket_api.async_register_command(hass, websocket_save_scene)
    websocket_api.async_register_command(hass, websocket_delete_scene)

    websocket_api.async_register_command(hass, websocket_get_aldb)
    websocket_api.async_register_command(hass, websocket_change_aldb_record)
    websocket_api.async_register_command(hass, websocket_create_aldb_record)
    websocket_api.async_register_command(hass, websocket_write_aldb)
    websocket_api.async_register_command(hass, websocket_load_aldb)
    websocket_api.async_register_command(hass, websocket_reset_aldb)
    websocket_api.async_register_command(hass, websocket_add_default_links)
    websocket_api.async_register_command(hass, websocket_notify_on_aldb_status)
    websocket_api.async_register_command(hass, websocket_add_x10_device)
    websocket_api.async_register_command(hass, websocket_remove_device)
    websocket_api.async_register_command(hass, websocket_notify_on_aldb_status_all)

    websocket_api.async_register_command(hass, websocket_get_properties)
    websocket_api.async_register_command(hass, websocket_change_properties_record)
    websocket_api.async_register_command(hass, websocket_write_properties)
    websocket_api.async_register_command(hass, websocket_load_properties)
    websocket_api.async_register_command(hass, websocket_reset_properties)

    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_get_modem_schema)
    websocket_api.async_register_command(hass, websocket_update_modem_config)
    websocket_api.async_register_command(hass, websocket_add_device_override)
    websocket_api.async_register_command(hass, websocket_remove_device_override)
    websocket_api.async_register_command(hass, websocket_get_broken_links)
    websocket_api.async_register_command(hass, websocket_get_unknown_devices)


async def async_register_insteon_frontend(hass: HomeAssistant):
    """Register the Insteon frontend configuration panel."""
    # Add to sidepanel if needed
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        dev_path = hass.data.get(DOMAIN, {}).get(CONF_DEV_PATH)
        is_dev = dev_path is not None
        path = dev_path if dev_path else locate_dir()
        build_id = get_build_id(is_dev)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, path, cache_headers=not is_dev)]
        )

        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="insteon-frontend",
            config_panel_domain=DOMAIN,
            module_url=f"{URL_BASE}/entrypoint-{build_id}.js",
            embed_iframe=True,
            require_admin=True,
        )
