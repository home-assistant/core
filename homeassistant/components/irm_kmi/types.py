"""Types definitions for IRM KMI integration."""

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import IRM_KMI_TO_HA_CONDITION_MAP, USER_AGENT
from .coordinator import IrmKmiCoordinator

type IrmKmiConfigEntry = ConfigEntry[RuntimeData]


class RuntimeData:
    """Data class for configuration entry runtime data."""

    api_client: IrmKmiApiClientHa
    coordinator: IrmKmiCoordinator

    def __init__(self, hass: HomeAssistant, entry: IrmKmiConfigEntry) -> None:
        """Construct RuntimeData using the config entry."""

        api_client = IrmKmiApiClientHa(
            session=async_get_clientsession(hass),
            user_agent=USER_AGENT,
            cdt_map=IRM_KMI_TO_HA_CONDITION_MAP,
        )

        self.api_client = api_client
        # If I don't put the api_client in the coordinator this way, I get circular dependencies.
        self.coordinator = IrmKmiCoordinator(hass, entry, api_client)
