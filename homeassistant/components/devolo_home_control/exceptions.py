"""Custom exceptions for the devolo_home_control integration."""
from homeassistant.exceptions import HomeAssistantError


class CredentialsInvalid(HomeAssistantError):
    """Given credentials are invalid."""
