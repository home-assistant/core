"""Exceptions for the Remootio integration."""
from aioremootio import RemootioClient, RemootioError

from homeassistant.exceptions import HomeAssistantError


class UnsupportedRemootioDeviceError(RemootioError):
    """Error to indicate unsupported Remootio device."""

    def __init__(
        self,
        device: RemootioClient,
        message="Your device isn't supported, possibly because it hasn't a sensor installed.",
    ) -> None:
        """Initialize the instance of this class."""

        super().__init__(device, message)


class UnsupportedRemootioApiVersionError(UnsupportedRemootioDeviceError):
    """Error to indicate unsupported Remootio API version."""

    def __init__(self, device: RemootioClient, api_version: int) -> None:
        """Initialize the instance of this class."""

        super().__init__(
            device,
            f"Your device isn't supported, because it uses a Remootio API version (v{api_version}) which isn't supported. Please update the software on your device at least to v2.21.",
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
