"""Home Assistant trigger dispatcher."""
import importlib

from homeassistant.const import CONF_PLATFORM


async def async_attach_trigger(hass, config, action, automation_info):
    """Attach trigger of specified platform."""
    return await importlib.import_module(
        f"../triggers/{config[CONF_PLATFORM]}", __name__
    ).async_attach_trigger(hass, config, action, automation_info)
