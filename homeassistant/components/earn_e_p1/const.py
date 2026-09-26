"""Constants for the EARN-E P1 Meter integration."""

from earn_e_p1 import EarnEP1Listener

from homeassistant.util.hass_dict import HassKey

DOMAIN = "earn_e_p1"
CONF_SERIAL = "serial"

# One UDP listener receives packets from every meter, so it is shared between
# config entries and reused by the config flow for discovery and validation.
EARN_E_P1_DATA: HassKey[EarnEP1Listener] = HassKey(DOMAIN)
