"""Support for my.home-assistant.io redirect service."""
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "my"
URL_PATH = "_my_redirect"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register hidden _my_redirect panel."""
    frontend.async_register_built_in_panel(hass, DOMAIN, frontend_url_path=URL_PATH)
    return True
