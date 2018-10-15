"""Lovelace UI."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.util.yaml import load_yaml
from homeassistant.exceptions import HomeAssistantError

DOMAIN = 'lovelace'

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'
SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): vol.Any(WS_TYPE_GET_LOVELACE_UI,
                                  OLD_WS_TYPE_GET_LOVELACE_UI),
})


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Backwards compat. Added in 0.80. Remove after 0.85
    hass.components.websocket_api.async_register_command(
        OLD_WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    return True


@websocket_api.async_response
async def websocket_lovelace_config(hass, connection, msg):
    """Send lovelace UI config over websocket config."""
    error = None
    try:
        config = await hass.async_add_executor_job(
            load_yaml, hass.config.path('ui-lovelace.yaml'))
        message = websocket_api.result_message(
            msg['id'], config
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except HomeAssistantError as err:
        error = 'load_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)
