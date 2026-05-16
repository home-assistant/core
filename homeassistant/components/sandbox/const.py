"""Constants for the Sandbox integration."""

from homeassistant.util.hass_dict import HassKey

DOMAIN = "sandbox"

DATA_SANDBOX: HassKey["SandboxData"] = HassKey(DOMAIN)
