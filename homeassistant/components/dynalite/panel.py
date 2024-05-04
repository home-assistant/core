"""Dynalite API interface for the frontend."""

from dynalite_panel import get_build_id, locate_dir
import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.cover import DEVICE_CLASSES
from homeassistant.const import CONF_DEFAULT, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ACTIVE,
    CONF_AREA,
    CONF_AUTO_DISCOVER,
    CONF_PRESET,
    CONF_TEMPLATE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)
from .schema import BRIDGE_SCHEMA

URL_BASE = "/dynalite_static"

RELEVANT_CONFS = [
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_AUTO_DISCOVER,
    CONF_AREA,
    CONF_DEFAULT,
    CONF_ACTIVE,
    CONF_PRESET,
    CONF_TEMPLATE,
]


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dynalite/get-config",
    }
)
@websocket_api.require_admin
@callback
def get_dynalite_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Retrieve the Dynalite config for the frontend."""
    entries = hass.config_entries.async_entries(DOMAIN)
    relevant_config = {
        entry.entry_id: {
            conf: entry.data[conf] for conf in RELEVANT_CONFS if conf in entry.data
        }
        for entry in entries
    }
    dynalite_defaults = {
        "DEFAULT_NAME": DEFAULT_NAME,
        "DEVICE_CLASSES": DEVICE_CLASSES,
        "DEFAULT_PORT": DEFAULT_PORT,
    }
    connection.send_result(
        msg["id"], {"config": relevant_config, "default": dynalite_defaults}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dynalite/save-config",
        vol.Required("entry_id"): str,
        vol.Required("config"): BRIDGE_SCHEMA,
    }
)
@websocket_api.require_admin
@callback
def save_dynalite_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Retrieve the Dynalite config for the frontend."""
    entry_id = msg["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        LOGGER.error(
            "Dynalite - received updated config for invalid entry - %s", entry_id
        )
        connection.send_result(msg["id"], {"error": True})
        return
    message_conf = msg["config"]
    message_data = {
        conf: message_conf[conf] for conf in RELEVANT_CONFS if conf in message_conf
    }
    LOGGER.info("Updating Dynalite config entry")
    hass.config_entries.async_update_entry(entry, data=message_data)
    connection.send_result(msg["id"], {})


async def async_register_dynalite_frontend(hass: HomeAssistant):
    """Register the Dynalite frontend configuration panel."""
    websocket_api.async_register_command(hass, get_dynalite_config)
    websocket_api.async_register_command(hass, save_dynalite_config)
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        path = locate_dir()
        build_id = get_build_id()
        hass.http.register_static_path(
            URL_BASE, path, cache_headers=(build_id != "dev")
        )

        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            config_panel_domain=DOMAIN,
            webcomponent_name="dynalite-panel",
            module_url=f"{URL_BASE}/entrypoint-{build_id}.js",
            embed_iframe=True,
            require_admin=True,
        )
