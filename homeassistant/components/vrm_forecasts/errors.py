from homeassistant.exceptions import HomeAssistantError  # noqa: D100


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class SiteNotFound(HomeAssistantError):
    """Error to indicate the site was not found."""
