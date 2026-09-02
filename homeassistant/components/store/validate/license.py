from __future__ import annotations

from typing import TYPE_CHECKING

from ..utils.json import json_loads
from .base import ActionValidationBase, ValidationException

if TYPE_CHECKING:
    from ..repositories.base import HacsRepository

# renovate: datasource=github-tags depName=spdx/license-list-data
SPDX_LICENSE_LIST_COMMIT = "c4a7237ec8f4654e867546f9f409749300f1bf4c"  # v3.28.0

SPDX_LICENSE_LIST_URL = (
    "https://raw.githubusercontent.com/spdx/license-list-data/"
    f"{SPDX_LICENSE_LIST_COMMIT}/json/licenses.json"
)

# OSI "Popular / Strong Community" licenses.
# https://opensource.org/licenses?categories=popular-strong-community
# Cached so the common case avoids fetching the full SPDX license list; only
# uncommon licenses fall back to the fetch below. SPDX IDs use the forms
# returned by GitHub's license API.
POPULAR_OSI_APPROVED_LICENSES = frozenset(
    {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "CDDL-1.0",
        "EPL-2.0",
        "GPL-2.0",
        "GPL-3.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "MIT",
        "MPL-2.0",
    }
)


async def async_setup_validator(repository: HacsRepository) -> Validator:
    """Set up this validator."""
    return Validator(repository=repository)


class Validator(ActionValidationBase):
    """Validate the repository."""

    more_info = "https://hacs.xyz/docs/publish/include#check-license"
    allow_fork = False

    async def async_validate(self) -> None:
        """Validate the repository."""
        if (license_info := self.repository.repository_object.attributes.get("license")) is None:
            raise ValidationException("The repository has no license")

        spdx_id = license_info.get("spdx_id")
        if not spdx_id:
            raise ValidationException("The repository license is missing an SPDX ID")
        if spdx_id == "NOASSERTION":
            raise ValidationException(
                "The repository license could not be identified (SPDX: NOASSERTION)"
            )

        if spdx_id in POPULAR_OSI_APPROVED_LICENSES:
            self.repository.logger.debug(
                "The repository has a popular OSI-approved license: %s",
                license_info.get("name"),
            )
            return

        result = await self.hacs.async_download_file(SPDX_LICENSE_LIST_URL, handle_rate_limit=True)
        if result is None:
            raise ValidationException("Could not fetch the SPDX license list")

        try:
            licenses = json_loads(result).get("licenses", [])
        except Exception as err:
            raise ValidationException("Could not parse the SPDX license list") from err

        osi_approved = {
            entry.get("licenseId")
            for entry in licenses
            if entry.get("isOsiApproved") and entry.get("licenseId")
        }

        if spdx_id not in osi_approved:
            raise ValidationException(
                f"The repository does not have an OSI-approved license (detected: '{spdx_id}')"
            )

        self.repository.logger.debug(
            "The repository has an OSI-approved license: %s", license_info.get("name")
        )
