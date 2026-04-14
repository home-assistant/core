"""Version functions for Home Assistant templates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from awesomeversion import AwesomeVersion

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class VersionExtension(BaseTemplateExtension):
    """Jinja2 extension for version functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the version extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "version",
                    self.version,
                    as_global=True,
                    as_filter=True,
                ),
            ],
        )

    @staticmethod
    def version(value: str) -> AwesomeVersion:
        """Filter and function to get version object of the value."""
        return AwesomeVersion(value)
