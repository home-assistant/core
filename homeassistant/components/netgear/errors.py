"""Errors for the Netgear component."""
from homeassistant.exceptions import HomeAssistantError


class NetgearException(HomeAssistantError):
    """Base class for Netgear exceptions."""


class CannotLoginException(NetgearException):
    """Unable to login to the router."""
