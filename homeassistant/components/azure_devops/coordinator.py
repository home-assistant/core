"""Define the Azure DevOps DataUpdateCoordinator."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Final

from aioazuredevops.client import DevOpsClient
from aioazuredevops.helper import (
    WorkItemTypeAndState,
    work_item_types_states_filter,
    work_items_by_type_and_state,
)
from aioazuredevops.models.build import Build
from aioazuredevops.models.core import Project
from aioazuredevops.models.work_item_type import Category
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ORG, DOMAIN
from .data import AzureDevOpsData

BUILDS_QUERY: Final = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"
IGNORED_CATEGORIES: Final[list[Category]] = [Category.COMPLETED, Category.REMOVED]

type AzureDevOpsConfigEntry = ConfigEntry[AzureDevOpsDataUpdateCoordinator]


def ado_exception_none_handler(func: Callable) -> Callable:
    """Handle exceptions or None to always return a value or raise."""

    async def handler(*args, **kwargs):
        try:
            response = await func(*args, **kwargs)
        except aiohttp.ClientError as exception:
            raise UpdateFailed from exception

        if response is None:
            raise UpdateFailed("No data returned from Azure DevOps")

        return response

    return handler


class AzureDevOpsDataUpdateCoordinator(DataUpdateCoordinator[AzureDevOpsData]):
    """Class to manage and fetch Azure DevOps data."""

    client: DevOpsClient
    config_entry: AzureDevOpsConfigEntry
    organization: str
    project: Project

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AzureDevOpsConfigEntry,
        logger: logging.Logger,
    ) -> None:
        """Initialize global Azure DevOps data updater."""
        self.title = config_entry.title

        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=300),
        )

        self.client = DevOpsClient(session=async_get_clientsession(hass))
        self.organization = config_entry.data[CONF_ORG]

    @ado_exception_none_handler
    async def authorize(
        self,
        personal_access_token: str,
    ) -> bool:
        """Authorize with Azure DevOps."""
        await self.client.authorize(
            personal_access_token,
            self.organization,
        )
        if not self.client.authorized:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={"title": self.title},
            )

        return True

    @ado_exception_none_handler
    async def get_project(
        self,
        project: str,
    ) -> Project | None:
        """Get the project."""
        return await self.client.get_project(
            self.organization,
            project,
        )

    @ado_exception_none_handler
    async def _get_builds(self, project_name: str) -> list[Build] | None:
        """Get the builds."""
        return await self.client.get_builds(
            self.organization,
            project_name,
            BUILDS_QUERY,
        )

    @ado_exception_none_handler
    async def _get_work_items(
        self, project_name: str
    ) -> list[WorkItemTypeAndState] | None:
        """Get the work items."""

        if (
            work_item_types := await self.client.get_work_item_types(
                self.organization,
                project_name,
            )
        ) is None:
            # If no work item types are returned, return an empty list
            return []

        if (
            work_item_ids := await self.client.get_work_item_ids(
                self.organization,
                project_name,
                # Filter out completed and removed work items so we only get active work items
                states=work_item_types_states_filter(
                    work_item_types,
                    ignored_categories=IGNORED_CATEGORIES,
                ),
            )
        ) is None:
            # If no work item ids are returned, return an empty list
            return []

        if (
            work_items := await self.client.get_work_items(
                self.organization,
                project_name,
                work_item_ids,
            )
        ) is None:
            # If no work items are returned, return an empty list
            return []

        return work_items_by_type_and_state(
            work_item_types,
            work_items,
            ignored_categories=IGNORED_CATEGORIES,
        )

    async def _async_update_data(self) -> AzureDevOpsData:
        """Fetch data from Azure DevOps."""
        # Get the builds from the project
        builds = await self._get_builds(self.project.name)
        work_items = await self._get_work_items(self.project.name)

        return AzureDevOpsData(
            organization=self.organization,
            project=self.project,
            builds=builds,
            work_items=work_items,
        )
