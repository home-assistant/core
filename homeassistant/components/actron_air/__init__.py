"""The Actron Air integration."""

from actron_neo_api import ActronAirAPI, ActronAirAPIError, ActronAirAuthError
from actron_neo_api.models.system import ActronAirSystemInfo

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import (
    ActronAirConfigEntry,
    ActronAirRuntimeData,
    ActronAirSystemCoordinator,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ActronAirConfigEntry) -> bool:
    """Set up Actron Air integration from a config entry."""

    api = ActronAirAPI(
        refresh_token=entry.data[CONF_API_TOKEN],
        session=async_get_clientsession(hass),
    )
    systems: list[ActronAirSystemInfo] = []

    try:
        systems = await api.get_ac_systems()
        await api.update_status()
    except ActronAirAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
        ) from err
    except ActronAirAPIError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
        ) from err

    try:
        push_enabled = await api.start_push(
            [system.serial for system in systems if system.serial]
        )
    except ActronAirAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
        ) from err

    if push_enabled:
        entry.async_on_unload(api.stop_push)
    else:
        LOGGER.debug("Realtime push unavailable, falling back to polling")

    device_registry = dr.async_get(hass)
    system_coordinators: dict[str, ActronAirSystemCoordinator] = {}
    for system in systems:
        coordinator = ActronAirSystemCoordinator(
            hass, entry, api, system, push_enabled=push_enabled
        )
        LOGGER.debug("Setting up coordinator for system: %s", system.serial)
        await coordinator.async_config_entry_first_refresh()
        system_coordinators[system.serial] = coordinator

        # Register the AC system device so zone and peripheral entities can link to
        # it as their via device when they are set up.
        ac_system = coordinator.data.ac_system
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, system.serial)},
            name=ac_system.system_name,
            manufacturer="Actron Air",
            model_id=ac_system.master_wc_model,
            sw_version=ac_system.master_wc_firmware_version,
            serial_number=system.serial,
        )

    entry.runtime_data = ActronAirRuntimeData(
        api=api,
        system_coordinators=system_coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronAirConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
