"""Component to embed Google Cast."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api

from . import home_assistant_cast
from .const import DOMAIN


async def async_setup(hass, config):
    """Set up the Cast component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass, entry: config_entries.ConfigEntry):
    """Set up Cast from a config entry."""
    websocket_api.async_register_command(hass, websocket_remove_device)

    await home_assistant_cast.async_setup_ha_cast(hass, entry)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True


@websocket_api.websocket_command(
    {vol.Required("type"): "cast/device/remove", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def websocket_remove_device(hass, connection, msg):
    """Delete device."""
    device_id = msg["device_id"]
    dev_registry = await hass.helpers.device_registry.async_get_registry()

    device = dev_registry.async_get(device_id)
    if not device:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Device not found"
        )
        return

    for config_entry in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry)
        # Only delete the device if it belongs to a Tasmota device entry
        if config_entry.domain == DOMAIN:
            dev_registry.async_remove_device(device_id)
            connection.send_message(websocket_api.result_message(msg["id"]))
            return

    connection.send_error(
        msg["id"], websocket_api.const.ERR_NOT_FOUND, "Non Google Cast device"
    )
