"""Custom API component for Home Assistant."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "custom_api"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Custom API component."""
    _LOGGER.info("Setting up Custom API component")
    
    # Register the API views
    from .api import CustomAPIView, CustomWebhookView
    hass.http.register_view(CustomAPIView())
    hass.http.register_view(CustomWebhookView())
    
    return True
