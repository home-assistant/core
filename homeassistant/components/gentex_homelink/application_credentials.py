"""application_credentials platform for the gentex homelink integration."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from . import oauth2


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, _credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return custom SRPAuth implementation."""
    return oauth2.SRPAuthImplementation(hass, auth_domain)
