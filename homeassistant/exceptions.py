"""The exceptions used by Home Assistant."""
import jinja2


class HomeAssistantError(Exception):
    """General Home Assistant exception occurred."""

    pass


class InvalidEntityFormatError(HomeAssistantError):
    """When an invalid formatted entity is encountered."""

    pass


class NoEntitySpecifiedError(HomeAssistantError):
    """When no entity is specified."""

    pass


class TemplateError(HomeAssistantError):
    """Error during template rendering."""

    def __init__(self, exception: jinja2.TemplateError) -> None:
        """Init the error."""
        super().__init__('{}: {}'.format(exception.__class__.__name__,
                                         exception))


class PlatformNotReady(HomeAssistantError):
    """Error to indicate that platform is not ready."""

    pass


class ConfigEntryNotReady(HomeAssistantError):
    """Error to indicate that config entry is not ready."""

    pass


class InvalidStateError(HomeAssistantError):
    """When an invalid state is encountered."""

    pass
