from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.hacs.enums import HacsCategory

from .base import ActionValidationBase, ValidationException

if TYPE_CHECKING:
    from ..repositories.base import HacsRepository

URL = "https://brands.home-assistant.io/domains.json"
ASSET_FILENAME = "icon.png"


async def async_setup_validator(repository: HacsRepository) -> Validator:
    """Set up this validator."""
    return Validator(repository=repository)


class Validator(ActionValidationBase):
    """Validate the repository."""

    more_info = "https://hacs.xyz/docs/publish/include#check-brands"
    categories = (HacsCategory.INTEGRATION,)

    async def async_validate(self) -> None:
        """Validate the repository."""

        treefiles = self.repository.treefiles

        if self.repository.repository_manifest.content_in_root:
            asset_path = f"brand/{ASSET_FILENAME}"
        else:
            asset_path = f"{self.repository.content.path.remote}/brand/{ASSET_FILENAME}"

        # Check if the integraiton provides local brand assets
        if asset_path in treefiles:
            self.repository.logger.debug("The repository contains brands assets at %s", asset_path)
            return

        self.repository.logger.warning(
            "The repository does not contain brands assets at %s. "
            "Falling back to checking the brands repository.",
            asset_path,
        )

        # Fallback the checking the Home Assistant brands repository for the domain
        response = await self.hacs.session.get(URL)
        content = await response.json()

        if self.repository.data.domain not in content["custom"]:
            raise ValidationException(
                "The repository does not provide brand assets "
                "and is not listed in the Home Assistant brands repository."
            )
