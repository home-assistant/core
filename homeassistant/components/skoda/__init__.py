"""The Škoda integration."""

from skoda_public_api.api_layer.open_api_client import OpenAPIClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_VIN
from .coordinator import SkodaConfigEntry, SkodaData, SkodaUpdateCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> None:
    """Set up Škoda from a config entry."""
    vin: str = entry.data[CONF_VIN]
    api_key: str = entry.data[CONF_API_KEY]

    session = async_get_clientsession(hass)
    openapi_client = OpenAPIClient(api_key=api_key, session=session)

    coordinator = SkodaUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=openapi_client,
        vin=vin,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SkodaData(
        openapi=openapi_client,
        coordinator=coordinator,
        vin=vin,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
