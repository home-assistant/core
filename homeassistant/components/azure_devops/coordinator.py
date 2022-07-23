"""DataUpdateCoordinator for Azure DevOps."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.client import DevOpsClient
from aioazuredevops.core import DevOpsProject
from aioazuredevops.wiql import DevOpsWiqlResult
from aioazuredevops.work_item import DevOpsWorkItemValue
import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ORG, CONF_PAT, CONF_PROJECT, DOMAIN

BUILDS_QUERY: Final = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"


@dataclass
class AzureDevOpsCoordinatorData:
    """Azure DevOps Coordinator Data."""

    builds: list[DevOpsBuild]
    work_items: list[DevOpsWorkItemValue]


class AzureDevOpsDataUpdateCoordinator(
    DataUpdateCoordinator[AzureDevOpsCoordinatorData]
):
    """Class to manage fetching Azure DevOps data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        LOGGER: logging.Logger,
        *,
        entry: ConfigEntry,
        client: DevOpsClient,
    ) -> None:
        """Initialize Azure DevOps data update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=300),
        )
        self._client = client
        self._organization = entry.data[CONF_ORG]
        self._pat = entry.data.get(CONF_PAT)
        self._project = entry.data[CONF_PROJECT]

    async def authorize(self) -> None:
        """Authenticate."""
        if self._pat is not None:
            await self._client.authorize(self._pat, self._organization)
            if not self._client.authorized:
                raise ConfigEntryAuthFailed(
                    "Could not authorize with Azure DevOps. You will need to update your token"
                )

    async def get_project(self) -> DevOpsProject:
        """Get project."""
        return await self._client.get_project(
            self._organization,
            self._project,
        )

    async def _async_update_data(self) -> AzureDevOpsCoordinatorData:
        """Fetch data from Azure DevOps."""
        try:
            async with async_timeout.timeout(30):
                try:
                    builds: list[DevOpsBuild] = await self._client.get_builds(
                        self._organization,
                        self._project,
                        BUILDS_QUERY,
                    )
                    if self._pat is not None:
                        wiql_result: DevOpsWiqlResult = (
                            await self._client.get_work_items_ids_all(
                                self._organization,
                                self._project,
                            )
                        )
                        if wiql_result:
                            ids: list[int] = [
                                item.id for item in wiql_result.work_items
                            ]
                            work_items: list[DevOpsWorkItemValue] = (
                                await self._client.get_work_items(
                                    self._organization,
                                    self._project,
                                    ids,
                                )
                            ).value

                            return AzureDevOpsCoordinatorData(
                                builds=builds,
                                work_items=work_items,
                            )

                    return AzureDevOpsCoordinatorData(
                        builds=builds,
                        work_items=[],
                    )
                except (aiohttp.ClientError, aiohttp.ClientError) as exception:
                    raise UpdateFailed from exception
        except (asyncio.TimeoutError) as exception:
            raise UpdateFailed from exception
