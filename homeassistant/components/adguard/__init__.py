"""Support for AdGuard Home."""

from adguardhome import AdGuardHome
from yarl import URL

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .coordinator import (
    AdGuardConfigEntry,
    AdGuardData,
    AdGuardHomeStateCoordinator,
    AdGuardHomeStatisticsCoordinator,
    AdGuardHomeUpdateCoordinator,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.UPDATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""

    async_setup_services(hass)
    return True


@callback
def _async_migrate_device_identifiers(
    hass: HomeAssistant, entry: AdGuardConfigEntry
) -> None:
    """Migrate devices identified by host, port and base path to the entry ID.

    Those identifiers had four parts, while the device registry only supports two.
    """
    device_registry = dr.async_get(hass)
    identifiers = {(DOMAIN, entry.entry_id)}
    migrated = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.identifiers == identifiers:
            continue

        # Downgrading recreates the old device, leaving a duplicate behind. Its
        # entities move back to the migrated device when the platforms set up.
        if migrated is not None:
            device_registry.async_remove_device(device.id)
            continue

        device_registry.async_update_device(device.id, new_identifiers=identifiers)


async def async_migrate_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Migrate an AdGuard Home config entry to the current version."""
    if entry.minor_version < 2:
        # Entities were identified by host and port, which change when
        # AdGuard Home moves. They are identified by the entry ID now.
        legacy_prefix = f"{DOMAIN}_{entry.data[CONF_HOST]}_{entry.data[CONF_PORT]}_"
        entity_registry = er.async_get(hass)

        @callback
        def _migrate_unique_id(entity: er.RegistryEntry) -> dict[str, str] | None:
            """Return the new unique ID of an entity with a legacy one."""
            if not entity.unique_id.startswith(legacy_prefix):
                return None

            # Like `sensor_dns_queries`, or just `update` for the update entity.
            legacy_key = entity.unique_id.removeprefix(legacy_prefix)
            if legacy_key == Platform.UPDATE:
                new_unique_id = entry.entry_id
            else:
                key = legacy_key.removeprefix(f"{entity.domain}_")
                new_unique_id = f"{entry.entry_id}_{key}"

            # Downgrading and upgrading again can leave both behind.
            if entity_registry.async_get_entity_id(
                entity.domain, DOMAIN, new_unique_id
            ):
                LOGGER.debug(
                    "Not migrating %s, %s is already in use",
                    entity.entity_id,
                    new_unique_id,
                )
                return None

            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Set up AdGuard Home from a config entry."""
    _async_migrate_device_identifiers(hass, entry)

    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    adguard = AdGuardHome(
        URL.build(
            scheme="https" if entry.data[CONF_SSL] else "http",
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        ),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
    )

    state = AdGuardHomeStateCoordinator(hass, entry, adguard)
    await state.async_config_entry_first_refresh()

    statistics = AdGuardHomeStatisticsCoordinator(hass, entry, adguard)
    await statistics.async_config_entry_first_refresh()

    # Checking for updates needs AdGuard Home to reach the internet, which not
    # every installation can. That should not keep the rest from working.
    update = AdGuardHomeUpdateCoordinator(hass, entry, adguard)
    await update.async_refresh()

    entry.runtime_data = AdGuardData(
        client=adguard, state=state, statistics=statistics, update=update
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Unload AdGuard Home config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
