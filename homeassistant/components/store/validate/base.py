"""Base class for validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import HacsException

if TYPE_CHECKING:
    from ..enums import HacsCategory
    from ..repositories.base import HacsRepository


class ValidationException(HacsException):
    """Raise when there is a validation issue."""


class ActionValidationBase:
    """Base class for action validation."""

    categories: tuple[HacsCategory, ...] = ()
    allow_fork: bool = True
    more_info: str = "https://hacs.xyz/docs/publish/action"

    def __init__(self, repository: HacsRepository) -> None:
        self.hacs = repository.hacs
        self.repository = repository
        self.failed = False

    @property
    def slug(self) -> str:
        """Return the check slug."""
        return self.__class__.__module__.rsplit(".", maxsplit=1)[-1]

    async def async_validate(self) -> None:
        """Validate the repository."""

    async def execute_validation(self, *_: Any, **__: Any) -> None:
        """Execute the task defined in subclass."""
        self.failed = False

        try:
            await self.async_validate()
        except ValidationException as exception:
            self.failed = True
            self.hacs.log.error(
                "<Validation %s> failed:  %s (More info: %s )",
                self.slug,
                exception,
                self.more_info,
            )

        else:
            self.hacs.log.info("<Validation %s> completed", self.slug)
