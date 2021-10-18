"""Web socket API for Z-Wave."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import callback

from .const import (
    CONF_AUTOHEAL,
    CONF_DEBUG,
    CONF_NETWORK_KEY,
    CONF_POLLING_INTERVAL,
    CONF_USB_STICK_PATH,
    DATA_NETWORK,
    DATA_ZWAVE_CONFIG,
)

TYPE = "type"
ID = "id"


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zwave/network_status"})
def websocket_network_status(hass, connection, msg):
    """Get Z-Wave network status."""
    network = hass.data[DATA_NETWORK]
    connection.send_result(msg[ID], {"state": network.state})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zwave/get_config"})
def websocket_get_config(hass, connection, msg):
    """Get Z-Wave configuration."""
    config = hass.data[DATA_ZWAVE_CONFIG]
    connection.send_result(
        msg[ID],
        {
            CONF_AUTOHEAL: config[CONF_AUTOHEAL],
            CONF_DEBUG: config[CONF_DEBUG],
            CONF_POLLING_INTERVAL: config[CONF_POLLING_INTERVAL],
            CONF_USB_STICK_PATH: config[CONF_USB_STICK_PATH],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required(TYPE): "zwave/get_migration_config"})
def websocket_get_migration_config(hass, connection, msg):
    """Get Z-Wave configuration for migration."""
    config = hass.data[DATA_ZWAVE_CONFIG]
    connection.send_result(
        msg[ID],
        {
            CONF_USB_STICK_PATH: config[CONF_USB_STICK_PATH],
            CONF_NETWORK_KEY: config[CONF_NETWORK_KEY],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required(TYPE): "zwave/start_zwave_js_config_flow"}
)
@websocket_api.async_response
async def websocket_start_zwave_js_config_flow(hass, connection, msg):
    """Start the Z-Wave JS integration config flow (for migration wizard).

    Return data with the flow id of the started Z-Wave JS config flow.
    """
    config = hass.data[DATA_ZWAVE_CONFIG]
    data = {
        "usb_path": config[CONF_USB_STICK_PATH],
        "network_key": config[CONF_NETWORK_KEY],
    }
    result = await hass.config_entries.flow.async_init(
        "zwave_js", context={"source": SOURCE_IMPORT}, data=data
    )
    connection.send_result(
        msg[ID],
        {"flow_id": result["flow_id"]},
    )


@callback
def async_load_websocket_api(hass):
    """Set up the web socket API."""
    websocket_api.async_register_command(hass, websocket_network_status)
    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_get_migration_config)
    websocket_api.async_register_command(hass, websocket_start_zwave_js_config_flow)
