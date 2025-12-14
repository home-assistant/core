"""Config flow for the Sleep as Android integration."""

from __future__ import annotations

from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

config_entry_flow.register_webhook_flow(
    DOMAIN,
    "Sleep as Android",
    {"docs_url": "https://www.home-assistant.io/integrations/sleep_as_android"},
    allow_multiple=True,
)
