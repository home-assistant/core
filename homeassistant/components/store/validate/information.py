from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ActionValidationBase, ValidationException

if TYPE_CHECKING:
    from ..repositories.base import HacsRepository


async def async_setup_validator(repository: HacsRepository) -> Validator:
    """Set up this validator."""
    return Validator(repository=repository)


class Validator(ActionValidationBase):
    """Validate the repository."""

    more_info = "https://hacs.xyz/docs/publish/include#check-info"

    async def async_validate(self) -> None:
        """Validate the repository."""
        filenames = [x.filename.lower() for x in self.repository.tree]
        if "readme" in filenames:
            pass
        elif "readme.md" in filenames:
            pass
        elif "info" in filenames:
            pass
        elif "info.md" in filenames:
            pass
        else:
            raise ValidationException("The repository has no information file")
