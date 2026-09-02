from __future__ import annotations

from voluptuous.error import Invalid
from voluptuous.humanize import humanize_error

from ..enums import HacsCategory, RepositoryFile
from ..repositories.base import HacsManifest, HacsRepository
from ..utils.validate import HACS_MANIFEST_JSON_SCHEMA
from .base import ActionValidationBase, ValidationException


async def async_setup_validator(repository: HacsRepository) -> Validator:
    """Set up this validator."""
    return Validator(repository=repository)


class Validator(ActionValidationBase):
    """Validate the repository."""

    more_info = "https://hacs.xyz/docs/publish/include#check-hacs-manifest"

    async def async_validate(self) -> None:
        """Validate the repository."""
        if RepositoryFile.HACS_JSON not in [x.filename for x in self.repository.tree]:
            raise ValidationException(f"The repository has no '{RepositoryFile.HACS_JSON}' file")

        rawhacsjson = await self.repository.get_hacs_json_raw(version=self.repository.ref)
        if rawhacsjson is None:
            raise ValidationException(
                f"The repository has an invalid '{RepositoryFile.HACS_JSON}' file"
            )

        try:
            hacsjson = HacsManifest.from_dict(HACS_MANIFEST_JSON_SCHEMA(rawhacsjson))
        except Invalid as exception:
            self.repository.logger.warning(
                "HACS JSON validation failed for: %s",
                rawhacsjson,
            )
            raise ValidationException(humanize_error(rawhacsjson, exception)) from exception

        if self.repository.data.category == HacsCategory.INTEGRATION:
            if hacsjson.zip_release and not hacsjson.filename:
                raise ValidationException("zip_release is True, but filename is not set")
