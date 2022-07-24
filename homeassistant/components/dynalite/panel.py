"""Dynalite API interface for the frontend."""

from dynalite_panel import get_build_id, locate_dir
import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from .const import CONF_AREA, CONF_DEV_PATH, DOMAIN

URL_BASE = "/dynalite_static"


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dynalite/get-config",
    }
)
@callback
def get_dynalite_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Retrieve the Dynalite config for the frontend."""
    relevant_confs = [CONF_HOST, CONF_PORT, CONF_AREA]
    entries = hass.config_entries.async_entries(DOMAIN)
    relevant_config = [
        {conf: entry.data[conf] for conf in relevant_confs if conf in entry.data}
        for entry in entries
    ]
    connection.send_result(msg["id"], {"config": relevant_config})


async def async_register_dynalite_frontend(hass: HomeAssistant):
    """Register the Dynalite frontend configuration panel."""
    # Add to sidepanel if needed
    websocket_api.async_register_command(hass, get_dynalite_config)
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        dev_path = hass.data.get(DOMAIN, {}).get(CONF_DEV_PATH)
        # is_dev = dev_path is not None XXX TODO
        is_dev = True
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
