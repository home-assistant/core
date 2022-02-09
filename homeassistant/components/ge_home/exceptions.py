""" Home Assistant derived exceptions"""

from homeassistant import exceptions as ha_exc

class HaCannotConnect(ha_exc.HomeAssistantError):
    """Error to indicate we cannot connect."""
class HaAuthError(ha_exc.HomeAssistantError):
    """Error to indicate authentication failure."""
class HaAlreadyConfigured(ha_exc.HomeAssistantError):
    """Error to indicate that the account is already configured"""