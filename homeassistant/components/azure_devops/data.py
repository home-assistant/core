"""Data classes for Azure DevOps integration."""

from dataclasses import dataclass

from aioazuredevops.models.builds import Build
from aioazuredevops.models.core import Project


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsData:
    """Class describing Azure DevOps data."""

    organization: str
    project: Project
    builds: list[Build]
