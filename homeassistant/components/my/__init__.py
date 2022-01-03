"""Support for my.home-assistant.io redirect service."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "my"
URL_PATH = "_my_redirect"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register hidden _my_redirect panel."""
    hass.components.frontend.async_register_built_in_panel(
        DOMAIN, frontend_url_path=URL_PATH
    )
    return True
