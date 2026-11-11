"""Const for Mailgun."""

from typing import Any

from homeassistant.util.hass_dict import HassKey

DOMAIN = "mailgun"

# YAML component config (api_key / domain / sandbox) used by notify + webhook verify.
# Domain-level, not per config entry — entries only register webhooks.
DATA_CONFIG: HassKey[dict[str, Any]] = HassKey(DOMAIN)
