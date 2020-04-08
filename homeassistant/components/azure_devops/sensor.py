"""Support for Azure DevOps sensors."""
from datetime import timedelta
import logging

from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v5_1.build import Build
from msrest.exceptions import ClientRequestError

from homeassistant.components.azure_devops import AzureDevOpsDeviceEntity
from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PROJECT,
    DATA_AZURE_DEVOPS_CONNECTION,
    DATA_ORG,
    DATA_PROJECT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Azure DevOps sensor based on a config entry."""
    instance_key = f"{DOMAIN}_{entry.data[CONF_ORG]}_{entry.data[CONF_PROJECT]}"
    connection = hass.data[instance_key][DATA_AZURE_DEVOPS_CONNECTION]
    organization = hass.data[instance_key][DATA_ORG]
    project = hass.data[instance_key][DATA_PROJECT]
    sensors = []

    try:
        build_client = connection.clients.get_build_client()
        builds = build_client.get_builds(
            project, query_order="queueTimeDescending", max_builds_per_definition=1,
        ).value
        for build in builds:
            sensors.append(
                AzureDevOpsLatestBuildSensor(build_client, organization, project, build)
            )
    except AzureDevOpsServiceError as exception:
        _LOGGER.warning(exception)
        raise PlatformNotReady from exception
    except ClientRequestError as exception:
        _LOGGER.warning(exception)
        raise PlatformNotReady from exception

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

    def __init__(self, client, organization: str, project: str, build: Build):
        """Initialize Azure DevOps sensor."""
        self.build = build
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
            build = self.client.get_build(self.build.project.id, self.build.id)
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
                # pylint:disable=protected-access
                "url": build._links.additional_properties["web"]["href"],
            }
            self._available = True
        except AzureDevOpsServiceError as exception:
            _LOGGER.warning(exception)
            self._available = False
        except ClientRequestError as exception:
            _LOGGER.warning(exception)
            self._available = False
        return True
