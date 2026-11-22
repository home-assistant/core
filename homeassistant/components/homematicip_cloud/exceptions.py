"""Exceptions for the Homematic IP Cloud integration."""

from homeassistant.exceptions import HomeAssistantError

DOMAIN = "homematicip_cloud"


class HeatingControlError(HomeAssistantError):
    """Error setting the heating control mode."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="heating_control_failed",
        )
