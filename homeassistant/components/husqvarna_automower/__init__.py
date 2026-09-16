"""The Husqvarna Automower integration."""

from aioautomower.exceptions import ApiError, AuthError
from aioautomower.session import AutomowerSession

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import api
from .const import DOMAIN
from .coordinator import AutomowerConfigEntry, AutomowerDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Migrate config entry."""
    if entry.minor_version < 2:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
        api_api = api.AsyncConfigEntryAuth(
            aiohttp_client.async_get_clientsession(hass), session
        )
        automower_api = AutomowerSession(
            api_api, await dt_util.async_get_time_zone(str(dt_util.DEFAULT_TIME_ZONE))
        )
        try:
            data = await automower_api.get_status()
        except AuthError:
            entry.async_start_reauth(hass)
            return False
        except ApiError:
            return False

        entity_registry = er.async_get(hass)
        for mower_id, mower_data in data.items():
            for work_area_id, work_area in (mower_data.work_areas or {}).items():
                if not work_area.use_global_cutting_height:
                    continue
                if entity_id := entity_registry.async_get_entity_id(
                    Platform.NUMBER,
                    DOMAIN,
                    f"{mower_id}_{work_area_id}_cutting_height_work_area",
                ):
                    entity_registry.async_remove(entity_id)

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Set up this integration using UI."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api_api = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass),
        session,
    )
    time_zone_str = str(dt_util.DEFAULT_TIME_ZONE)
    automower_api = AutomowerSession(
        api_api,
        await dt_util.async_get_time_zone(time_zone_str),
    )
    await api_api.async_get_access_token()

    if "amc:api" not in entry.data["token"]["scope"]:
        # We raise ConfigEntryAuthFailed here because the websocket can't be used
        # without the scope. So only polling would be possible.
        raise ConfigEntryAuthFailed

    coordinator = AutomowerDataUpdateCoordinator(hass, entry, automower_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.client_listen(hass, entry, automower_api),
        "websocket_task",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
