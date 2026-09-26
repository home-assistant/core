"""Constants for the Zerproc integration."""

from homeassistant.core import CALLBACK_TYPE
from homeassistant.util.hass_dict import HassKey

DOMAIN = "zerproc"

# Addresses of the lights discovered so far. Shared by every config entry so
# that recurring discovery does not add the same light twice.
DATA_ADDRESSES: HassKey[set[str]] = HassKey(f"{DOMAIN}_addresses")

# Cancels the recurring discovery. Registered by the light platform and called
# when the entry unloads.
DATA_DISCOVERY_SUBSCRIPTION: HassKey[CALLBACK_TYPE] = HassKey(
    f"{DOMAIN}_discovery_subscription"
)
