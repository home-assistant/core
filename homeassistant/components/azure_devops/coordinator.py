"""Define the Azure DevOps DataUpdateCoordinator."""

from datetime import timedelta
import logging
from typing import Final

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.client import DevOpsClient
from aioazuredevops.core import DevOpsProject
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ORG, CONF_PROJECT, DOMAIN
from .data import AzureDevOpsData

BUILDS_QUERY: Final = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"


class AzureDevOpsDataUpdateCoordinator(DataUpdateCoordinator[AzureDevOpsData]):
    """Class to manage and fetch Azure DevOps data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global Azure DevOps data updater."""
        self.title = entry.title

        super().__init__(
            hass=hass,
            logger=logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=300),
        )

        self.client = DevOpsClient(session=async_get_clientsession(hass))
        self.organization = entry.data[CONF_ORG]
        self.project_name = entry.data[CONF_PROJECT]

    async def authorize(
        self,
        personal_access_token: str,
    ) -> None:
        """Authorize with Azure DevOps."""
        await self.client.authorize(
            personal_access_token,
            self.organization,
        )
        if not self.client.authorized:
            raise ConfigEntryAuthFailed(
                "Could not authorize with Azure DevOps. You will need to update your"
                " token"
            )

    async def _get_project(
        self,
        project: str,
    ) -> DevOpsProject | None:
        """Get the project."""
        return await self.client.get_project(
            self.organization,
            project,
        )

    async def _get_builds(self, project_name: str) -> list[DevOpsBuild] | None:
        """Get the builds."""
        return await self.client.get_builds(
            self.organization,
            project_name,
            BUILDS_QUERY,
        )

    async def _async_update_data(self) -> AzureDevOpsData:
        """Fetch data from Azure DevOps."""
        try:
            # Get the project if we haven't already
            if self.data is None or (project := self.data.project) is None:
                project = await self._get_project(self.project_name)
                if project is None:
                    raise UpdateFailed("No project found")

            # Get the builds from the project
            builds = await self._get_builds(project.name)
        except aiohttp.ClientError as exception:
            raise UpdateFailed from exception

        if builds is None:
            raise UpdateFailed("No builds found")

        return AzureDevOpsData(
            organization=self.organization,
            project=project,
            builds=builds,
        )
