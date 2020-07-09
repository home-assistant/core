"""The exceptions used by Home Assistant."""
from typing import TYPE_CHECKING, Optional

import jinja2

if TYPE_CHECKING:
    from .core import Context  # noqa: F401 pylint: disable=unused-import


class HomeAssistantError(Exception):
    """General Home Assistant exception occurred."""


class InvalidEntityFormatError(HomeAssistantError):
    """When an invalid formatted entity is encountered."""


class NoEntitySpecifiedError(HomeAssistantError):
    """When no entity is specified."""


class TemplateError(HomeAssistantError):
    """Error during template rendering."""

    def __init__(self, exception: jinja2.TemplateError) -> None:
        """Init the error."""
        super().__init__(f"{exception.__class__.__name__}: {exception}")


class PlatformNotReady(HomeAssistantError):
    """Error to indicate that platform is not ready."""


class ConfigEntryNotReady(HomeAssistantError):
    """Error to indicate that config entry is not ready."""


class InvalidStateError(HomeAssistantError):
    """When an invalid state is encountered."""


class Unauthorized(HomeAssistantError):
    """When an action is unauthorized."""

    def __init__(
        self,
        context: Optional["Context"] = None,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        config_entry_id: Optional[str] = None,
        perm_category: Optional[str] = None,
        permission: Optional[str] = None,
    ) -> None:
        """Unauthorized error."""
        super().__init__(self.__class__.__name__)
        self.context = context
        self.user_id = user_id
        self.entity_id = entity_id
        self.config_entry_id = config_entry_id
        # Not all actions have an ID (like adding config entry)
        # We then use this fallback to know what category was unauth
        self.perm_category = perm_category
        self.permission = permission


class UnknownUser(Unauthorized):
    """When call is made with user ID that doesn't exist."""


class ServiceNotFound(HomeAssistantError):
    """Raised when a service is not found."""

    def __init__(self, domain: str, service: str) -> None:
        """Initialize error."""
        super().__init__(self, f"Service {domain}.{service} not found")
        self.domain = domain
        self.service = service

    def __str__(self) -> str:
        """Return string representation."""
        return f"Unable to find service {self.domain}/{self.service}"
