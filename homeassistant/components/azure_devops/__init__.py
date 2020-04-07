"""Support for Azure DevOps."""
import logging
from typing import Any, Dict

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

from homeassistant.components.azure_devops.const import (
    CONF_ORG,
    CONF_PAT,
    CONF_PROJECT,
    DATA_AZURE_DEVOPS_CONNECTION,
    DATA_ORG,
    DATA_PAT,
    DATA_PROJECT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Azure DevOps components."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Azure DevOps from a config entry."""
    connection = Connection(
        base_url=f"https://dev.azure.com/{entry.data[CONF_ORG]}",
        creds=BasicAuthentication("", entry.data[CONF_PAT]),
    )

    instance_key = f"{DOMAIN}_{entry.data[CONF_ORG]}_{entry.data[CONF_PROJECT]}"
    hass.data.setdefault(instance_key, {})[DATA_AZURE_DEVOPS_CONNECTION] = connection
    hass.data.setdefault(instance_key, {})[DATA_ORG] = entry.data[CONF_ORG]
    hass.data.setdefault(instance_key, {})[DATA_PROJECT] = entry.data[CONF_PROJECT]
    hass.data.setdefault(instance_key, {})[DATA_PAT] = entry.data[CONF_PAT]

    # Setup sensors
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload Azure DevOps config entry."""
    # Unload sensors
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    del hass.data[DOMAIN]

    return True


class AzureDevOpsEntity(Entity):
    """Defines a base Azure DevOps entity."""

    def __init__(self, organization: str, project: str, name: str, icon: str) -> None:
        """Initialize the Azure DevOps entity."""
        self._name = name
        self._icon = icon
        self._available = True
        self.organization = organization
        self.project = project

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update Azure DevOps entity."""
        if await self._azure_devops_update():
            self._available = True
        else:
            if self._available:
                _LOGGER.debug(
                    "An error occurred while updating Azure DevOps sensor.",
                    exc_info=True,
                )
            self._available = False

    async def _azure_devops_update(self) -> None:
        """Update Azure DevOps entity."""
        raise NotImplementedError()


class AzureDevOpsDeviceEntity(AzureDevOpsEntity):
    """Defines a Azure DevOps device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Azure DevOps instance."""
        return {
            "identifiers": {(DOMAIN, self.organization, self.project,)},
            "manufacturer": self.organization,
            "name": self.project,
        }
