"""The fitbit component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import FitbitScope
from .coordinator import FitbitConfigEntry, FitbitData, FitbitDeviceCoordinator
from .exceptions import FitbitApiException, FitbitAuthException
from .model import config_from_entry_data

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FitbitConfigEntry) -> bool:
    """Set up fitbit from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    fitbit_api = api.OAuthFitbitApi(
        hass, session, unit_system=entry.data.get("unit_system")
    )
    try:
        await fitbit_api.async_get_access_token()
    except FitbitAuthException as err:
        raise ConfigEntryAuthFailed from err
    except FitbitApiException as err:
        raise ConfigEntryNotReady from err

    fitbit_config = config_from_entry_data(entry.data)
    coordinator: FitbitDeviceCoordinator | None = None
    if fitbit_config.is_allowed_resource(FitbitScope.DEVICE, "devices/battery"):
        coordinator = FitbitDeviceCoordinator(hass, entry, fitbit_api)
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = FitbitData(api=fitbit_api, device_coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FitbitConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
