"""Data classes for Azure DevOps integration."""

from dataclasses import dataclass

from aioazuredevops.helper import WorkItemTypeAndState
from aioazuredevops.models.build import Build
from aioazuredevops.models.core import Project


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsData:
    """Class describing Azure DevOps data."""

    organization: str
    project: Project
    builds: list[Build]
    work_items: list[WorkItemTypeAndState]
