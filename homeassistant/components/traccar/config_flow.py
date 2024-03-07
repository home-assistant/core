"""Config flow for Traccar Client."""
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

config_entry_flow.register_webhook_flow(
    DOMAIN,
    "Traccar Client Webhook",
    {"docs_url": "https://www.home-assistant.io/integrations/traccar/"},
)
