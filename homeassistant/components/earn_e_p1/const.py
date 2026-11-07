"""Constants for the EARN-E P1 Meter integration."""

from homeassistant.util.hass_dict import HassKey

from .models import EarnEP1Data

DOMAIN = "earn_e_p1"
CONF_SERIAL = "serial"

# One UDP listener receives packets from every meter, so it is shared between
# config entries and reused by the config flow for discovery and validation.
EARN_E_P1_DATA: HassKey[EarnEP1Data] = HassKey(DOMAIN)
