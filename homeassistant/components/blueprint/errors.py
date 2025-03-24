"""Blueprint errors."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.exceptions import HomeAssistantError


class BlueprintException(HomeAssistantError):
    """Base exception for blueprint errors."""

    def __init__(self, domain: str | None, msg: str) -> None:
        """Initialize a blueprint exception."""
        super().__init__(msg)
        self.domain = domain


class BlueprintWithNameException(BlueprintException):
    """Base exception for blueprint errors."""

    def __init__(
        self, domain: str | None, blueprint_name: str | None, msg: str
    ) -> None:
        """Initialize blueprint exception."""
        super().__init__(domain, msg)
        self.blueprint_name = blueprint_name


class FailedToLoad(BlueprintWithNameException):
    """When we failed to load the blueprint."""

    def __init__(self, domain: str, blueprint_name: str, exc: Exception) -> None:
        """Initialize blueprint exception."""
        super().__init__(domain, blueprint_name, f"Failed to load blueprint: {exc}")


class InvalidBlueprint(BlueprintWithNameException):
    """When we encountered an invalid blueprint."""

    def __init__(
        self,
        domain: str | None,
        blueprint_name: str | None,
        blueprint_data: Any,
        msg_or_exc: str | vol.Invalid,
    ) -> None:
        """Initialize an invalid blueprint error."""
        if isinstance(msg_or_exc, vol.Invalid):
            msg_or_exc = humanize_error(blueprint_data, msg_or_exc)

        super().__init__(
            domain,
            blueprint_name,
            f"Invalid blueprint: {msg_or_exc}",
        )
        self.blueprint_data = blueprint_data


class InvalidBlueprintInputs(BlueprintException):
    """When we encountered invalid blueprint inputs."""

    def __init__(self, domain: str, msg: str) -> None:
        """Initialize an invalid blueprint inputs error."""
        super().__init__(
            domain,
            f"Invalid blueprint inputs: {msg}",
        )


class MissingInput(BlueprintWithNameException):
    """When we miss an input."""

    def __init__(
        self, domain: str, blueprint_name: str, input_names: Iterable[str]
    ) -> None:
        """Initialize blueprint exception."""
        super().__init__(
            domain,
            blueprint_name,
            f"Missing input {', '.join(sorted(input_names))}",
        )


class FileAlreadyExists(BlueprintWithNameException):
    """Error when file already exists."""

    def __init__(self, domain: str, blueprint_name: str) -> None:
        """Initialize blueprint exception."""
        super().__init__(domain, blueprint_name, "Blueprint already exists")


class BlueprintInUse(BlueprintWithNameException):
    """Error when a blueprint is in use."""

    def __init__(self, domain: str, blueprint_name: str) -> None:
        """Initialize blueprint exception."""
        super().__init__(domain, blueprint_name, "Blueprint in use")
