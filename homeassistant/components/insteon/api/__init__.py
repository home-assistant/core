"""Insteon API interface for the frontend."""
from insteon_frontend import locate_dir

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.insteon.const import CONF_DEV_URL, DOMAIN
from homeassistant.core import HomeAssistant, callback

from .aldb import (
    websocket_add_default_links,
    websocket_change_aldb_record,
    websocket_create_aldb_record,
    websocket_get_aldb,
    websocket_load_aldb,
    websocket_notify_on_aldb_status,
    websocket_reset_aldb,
    websocket_write_aldb,
)
from .device import (
    websocket_add_device,
    websocket_cancel_add_device,
    websocket_get_device,
    websocket_notify_on_device_added,
)
from .insteon_dev_view import InsteonFrontendDev
from .properties import (
    websocket_change_properties_record,
    websocket_get_properties,
    websocket_load_properties,
    websocket_reset_properties,
    websocket_write_properties,
)

URL_BASE = "/insteonfiles"


@callback
def async_load_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_get_device)
    websocket_api.async_register_command(hass, websocket_add_device)
    websocket_api.async_register_command(hass, websocket_notify_on_device_added)
    websocket_api.async_register_command(hass, websocket_cancel_add_device)

    websocket_api.async_register_command(hass, websocket_get_aldb)
    websocket_api.async_register_command(hass, websocket_change_aldb_record)
    websocket_api.async_register_command(hass, websocket_create_aldb_record)
    websocket_api.async_register_command(hass, websocket_write_aldb)
    websocket_api.async_register_command(hass, websocket_load_aldb)
    websocket_api.async_register_command(hass, websocket_reset_aldb)
    websocket_api.async_register_command(hass, websocket_add_default_links)
    websocket_api.async_register_command(hass, websocket_notify_on_aldb_status)

    websocket_api.async_register_command(hass, websocket_get_properties)
    websocket_api.async_register_command(hass, websocket_change_properties_record)
    websocket_api.async_register_command(hass, websocket_write_properties)
    websocket_api.async_register_command(hass, websocket_load_properties)
    websocket_api.async_register_command(hass, websocket_reset_properties)


async def async_register_insteon_frontend(hass: HomeAssistant):
    """Register the Insteon frontend configuration panel."""
    dev_url = hass.data.get(DOMAIN, {}).get(CONF_DEV_URL)
    if dev_url:
        hass.http.register_view(InsteonFrontendDev(hass, dev_url))
    else:
        hass.http.register_static_path(URL_BASE, locate_dir(), cache_headers=False)
    # Add to sidepanel if needed
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="insteon-frontend",
            sidebar_title=DOMAIN.capitalize(),
            sidebar_icon="mdi:power",
            module_url=f"{URL_BASE}/entrypoint.js",
            embed_iframe=True,
            require_admin=True,
        )
