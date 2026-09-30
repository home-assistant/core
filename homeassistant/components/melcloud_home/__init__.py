"""The MELCloud Home integration."""

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuth

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    MelCloudHomeConfigEntry,
    MelCloudHomeCoordinator,
    MelCloudHomeRuntimeData,
    MelCloudHomeTelemetryCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

UNIQUE_ID_KEYS: dict[str, str] = {
    Platform.CLIMATE: "ata_unit",
    Platform.WATER_HEATER: "hot_water",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Set up MELCloud Home from a config entry."""
    session = async_get_clientsession(hass)
    auth = MelCloudHomeAuth(
        username=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    client = MELCloudHome(auth=auth, session=session)

    coordinator = MelCloudHomeCoordinator(hass, entry, client)
    telemetry_coordinator = MelCloudHomeTelemetryCoordinator(hass, entry, client)

    # It has to be this order, to avoid a race condition
    await coordinator.async_config_entry_first_refresh()
    await telemetry_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MelCloudHomeRuntimeData(
        coordinator=coordinator,
        telemetry_coordinator=telemetry_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: MelCloudHomeConfigEntry
) -> bool:
    """Migrate old config entries."""
    if entry.minor_version < 2:

        @callback
        def _add_key_to_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            # Unit ids are UUIDs, so only bare unit ids lack an underscore
            if (
                key := UNIQUE_ID_KEYS.get(entity_entry.domain)
            ) is None or "_" in entity_entry.unique_id:
                return None
            return {"new_unique_id": f"{entity_entry.unique_id}_{key}"}

        await er.async_migrate_entries(hass, entry.entry_id, _add_key_to_unique_id)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True
