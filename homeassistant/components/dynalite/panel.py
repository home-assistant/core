"""Dynalite API interface for the frontend."""

from dynalite_panel import get_build_id, locate_dir

from homeassistant.components import panel_custom
from homeassistant.core import HomeAssistant

from .const import CONF_DEV_PATH, DOMAIN

URL_BASE = "/dynalite_static"


async def async_register_dynalite_frontend(hass: HomeAssistant):
    """Register the Dynalite frontend configuration panel."""
    # Add to sidepanel if needed
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        dev_path = hass.data.get(DOMAIN, {}).get(CONF_DEV_PATH)
        is_dev = dev_path is not None
        path = dev_path if dev_path else locate_dir()
        build_id = get_build_id(is_dev)
        hass.http.register_static_path(URL_BASE, path, cache_headers=not is_dev)

        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="dynalite-panel",
            sidebar_title=DOMAIN.capitalize(),
            sidebar_icon="mdi:power",
            module_url=f"{URL_BASE}/entrypoint-{build_id}.js",
            embed_iframe=True,
            require_admin=True,
        )
