"""Support for Azure DevOps sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioazuredevops.builds import DevOpsBuild
from aioazuredevops.client import DevOpsClient
import aiohttp

from homeassistant.components.azure_devops import AzureDevOpsDeviceEntity
from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PROJECT,
    DATA_AZURE_DEVOPS_CLIENT,
    DATA_ORG,
    DATA_PROJECT,
    DOMAIN,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4

BUILDS_QUERY = "?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    instance_key = f"{DOMAIN}_{entry.data[CONF_ORG]}_{entry.data[CONF_PROJECT]}"
    client = hass.data[instance_key][DATA_AZURE_DEVOPS_CLIENT]
    organization = entry.data[DATA_ORG]
    project = entry.data[DATA_PROJECT]
    sensors = []

    try:
        builds: list[DevOpsBuild] = await client.get_builds(
            organization, project, BUILDS_QUERY
        )
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise PlatformNotReady from exception

    for build in builds:
        sensors.append(
            AzureDevOpsLatestBuildSensor(client, organization, project, build)
        )

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity, SensorEntity):
    """Defines a Azure DevOps sensor."""

    def __init__(
        self,
        client: DevOpsClient,
        organization: str,
        project: str,
        key: str,
        name: str,
        icon: str,
        measurement: str = "",
        unit_of_measurement: str = "",
    ) -> None:
        """Initialize Azure DevOps sensor."""
        self._state = None
        self._attributes = None
        self._available = False
        self._unit_of_measurement = unit_of_measurement
        self.measurement = measurement
        self.client = client
        self.organization = organization
        self.project = project
        self.key = key

        super().__init__(organization, project, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join([self.organization, self.key])

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class AzureDevOpsLatestBuildSensor(AzureDevOpsSensor):
    """Defines a Azure DevOps card count sensor."""

    def __init__(
        self, client: DevOpsClient, organization: str, project: str, build: DevOpsBuild
    ):
        """Initialize Azure DevOps sensor."""
        self.build: DevOpsBuild = build
        super().__init__(
            client,
            organization,
            project,
            f"{build.project.id}_{build.definition.id}_latest_build",
            f"{build.project.name} {build.definition.name} Latest Build",
            "mdi:pipe",
        )

    async def _azure_devops_update(self) -> bool:
        """Update Azure DevOps entity."""
        try:
            build: DevOpsBuild = await self.client.get_build(
                self.organization, self.project, self.build.id
            )
        except aiohttp.ClientError as exception:
            _LOGGER.warning(exception)
            self._available = False
            return False
        self._state = build.build_number
        self._attributes = {
            "definition_id": build.definition.id,
            "definition_name": build.definition.name,
            "id": build.id,
            "reason": build.reason,
            "result": build.result,
            "source_branch": build.source_branch,
            "source_version": build.source_version,
            "status": build.status,
            "url": build.links.web,
            "queue_time": build.queue_time,
            "start_time": build.start_time,
            "finish_time": build.finish_time,
        }
        self._available = True
        return True
