"""The Lovelace Notify integration."""

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .serve_js import auto_load_ll_notify_js
from .services import setup_services


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up integration."""
    await setup_services(hass, config)
    await hass.services.async_call(DOMAIN, "get_defaults")
    await auto_load_ll_notify_js(hass, config)

    # hass.async_add_job(test.send_every_five(hass))

    return True
