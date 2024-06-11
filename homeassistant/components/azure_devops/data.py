"""Data classes for Azure DevOps integration."""

from dataclasses import dataclass

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.core import DevOpsProject


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsData:
    """Class describing Azure DevOps data."""

    organization: str
    project: DevOpsProject
    builds: list[DevOpsBuild]
