"""Support for Azure DevOps sensors."""
from datetime import timedelta
import logging

from homeassistant.components.azure_devops import AzureDevOpsDeviceEntity
from homeassistant.components.azure_devops.const import (
    DATA_AZURE_DEVOPS_CONNECTION,
    DATA_ORG,
    DATA_PROJECT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    connection = hass.data[DOMAIN][DATA_AZURE_DEVOPS_CONNECTION]
    organization = hass.data[DOMAIN][DATA_ORG]
    project = hass.data[DOMAIN][DATA_PROJECT]
    sensors = []

    build_client = connection.clients.get_build_client()

    builds = build_client.get_builds(
        project, query_order="queueTimeDescending", max_builds_per_definition=1
    ).value
    for build in builds:
        sensors.append(
            AzureDevOpsLatestBuildSensor(build_client, organization, project, build)
        )

    async_add_entities(sensors, True)


class AzureDevOpsSensor(AzureDevOpsDeviceEntity):
    """Defines a Azure DevOps sensor."""

    def __init__(
        self,
        client,
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
        return "_".join([DOMAIN, self.organization, self.key])

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class AzureDevOpsLatestBuildSensor(AzureDevOpsSensor):
    """Defines a Azure DevOps card count sensor."""

    def __init__(self, client, organization: str, project: str, build):
        """Initialize Azure DevOps sensor."""
        self.build = build
        super().__init__(
            client,
            organization,
            project,
            f"{build.project.id}_{build.definition.id}_latest_build",
            f"{project} {build.definition.name} Latest Build",
            "mdi:pipe",
        )

    async def _azure_devops_update(self) -> bool:
        """Update Azure DevOps entity."""
        build = self.client.get_build(self.project, self.build.id)
        self._state = build.build_number
        self._attributes = {
            "definition_id": build.definition.id,
            "definition_name": build.definition.name,
            "finish_time": build.finish_time,
            "id": build.id,
            "queue_time": build.queue_time,
            "reason": build.reason,
            "result": build.result,
            "source_branch": build.source_branch,
            "source_version": build.source_version,
            "start_time": build.start_time,
            "status": build.status,
            "url": build._links.additional_properties["web"]["href"],
        }
        return True
