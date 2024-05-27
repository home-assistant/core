"""Config flow for Switcher integration."""

from __future__ import annotations

from homeassistant.helpers import config_entry_flow

from .const import DOMAIN
from .utils import async_has_devices

config_entry_flow.register_discovery_flow(DOMAIN, "Switcher", async_has_devices)
