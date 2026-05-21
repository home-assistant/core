"""Comelit integration."""

from aiocomelit.const import BRIDGE

from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import _LOGGER, CONF_VEDO_PIN, DEFAULT_PORT, DOMAIN
from .coordinator import (
    ComelitBaseCoordinator,
    ComelitConfigEntry,
    ComelitSerialBridge,
    ComelitVedoSystem,
)
from .utils import async_client_session

BRIDGE_PLATFORMS = [
    Platform.CLIMATE,
    Platform.COVER,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
BRIDGE_AND_VEDO_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
VEDO_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ComelitConfigEntry) -> bool:
    """Set up Comelit platform."""

    coordinator: ComelitBaseCoordinator

    session = await async_client_session(hass)

    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        vedo_pin = entry.data.get(CONF_VEDO_PIN)
        coordinator = ComelitSerialBridge(
            hass,
            entry,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
            vedo_pin,
            session,
        )
        platforms = BRIDGE_PLATFORMS
        # Add VEDO platforms if vedo_pin is configured
        if vedo_pin:
            platforms = BRIDGE_AND_VEDO_PLATFORMS
    else:
        coordinator = ComelitVedoSystem(
            hass,
            entry,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
            session,
        )
        platforms = VEDO_PLATFORMS

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ComelitConfigEntry
) -> bool:
    """Migrate old entry."""

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1 and config_entry.minor_version == 1:
        device_registry = dr.async_get(hass)

        @callback
        def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
            if (
                entry.domain != Platform.SENSOR
                or entry.device_id is None
                or not (device_entry := device_registry.async_get(entry.device_id))
                or not any(
                    platform == DOMAIN
                    and identifier.startswith(f"{config_entry.entry_id}-zone-")
                    for platform, identifier in device_entry.identifiers
                )
            ):
                return None

            _LOGGER.debug(
                "Migrating from version %s.%s",
                config_entry.version,
                config_entry.minor_version,
            )

            zone_index = entry.unique_id.removeprefix(f"{config_entry.entry_id}-")
            return {
                "new_unique_id": f"{config_entry.entry_id}-human_status-{zone_index}"
            }

        await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

        hass.config_entries.async_update_entry(config_entry, version=1, minor_version=2)

        _LOGGER.info(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ComelitConfigEntry) -> bool:
    """Unload a config entry."""

    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        platforms = BRIDGE_PLATFORMS
        # Add VEDO platforms if vedo_pin was configured
        if entry.data.get(CONF_VEDO_PIN):
            platforms = BRIDGE_AND_VEDO_PLATFORMS
    else:
        platforms = VEDO_PLATFORMS

    coordinator = entry.runtime_data
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        await coordinator.api.logout()

    return unload_ok
