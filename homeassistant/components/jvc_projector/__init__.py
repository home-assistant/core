"""The jvc_projector integration."""

from __future__ import annotations

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorTimeoutError

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

from .const import DOMAIN
from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: JVCConfigEntry) -> bool:
    """Set up integration from a config entry."""
    device = JvcProjector(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await device.connect()
    except JvcProjectorTimeoutError as err:
        await device.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_HOST]}"
        ) from err
    except JvcProjectorAuthError as err:
        await device.disconnect()
        raise ConfigEntryAuthFailed("Password authentication failed") from err

    coordinator = JvcProjectorDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    async def disconnect(event: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    await async_migrate_entities(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JVCConfigEntry) -> bool:
    """Unload config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.device.disconnect()
    return unload_ok


async def async_migrate_entities(
    hass: HomeAssistant,
    config_entry: JVCConfigEntry,
    coordinator: JvcProjectorDataUpdateCoordinator,
) -> None:
    """Migrate old entities as needed."""
    entity_registry = er.async_get(hass)

    # Fix legacy unique_id of power binary_sensor entry. Can be removed ~2027.3+.

    @callback
    def _update_entry(entry: RegistryEntry) -> dict[str, str] | None:
        """Generate a new unique_id for power binary_sensor entry."""
        if entry.domain == Platform.BINARY_SENSOR and ":" not in entry.unique_id:
            if entry.unique_id.endswith("_power"):
                return {"new_unique_id": f"{coordinator.unique_id}_power"}
        return None

    await async_migrate_entries(hass, config_entry.entry_id, _update_entry)

    # Move legacy sensor entities that became selects. Can be removed ~2027.3+.

    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if (
            entry.platform != DOMAIN
            or entry.domain != Platform.SENSOR
            or entry.translation_key not in ("hdr_processing", "picture_mode")
        ):
            continue

        entity_id = entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, entry.unique_id
        )

        new_entry = entity_registry.async_get_or_create(
            Platform.SELECT,
            DOMAIN,
            entry.unique_id,
            config_entry=config_entry,
            device_id=entry.device_id,
            object_id_base=entry.object_id_base,
            has_entity_name=entry.has_entity_name,
            disabled_by=entry.disabled_by,
        )

        if entity_id is None:
            entity_registry.async_update_entity(
                new_entry.entity_id,
                area_id=entry.area_id,
                categories=entry.categories,
                hidden_by=entry.hidden_by,
                icon=entry.icon,
                labels=entry.labels,
                name=entry.name,
            )

        entity_registry.async_remove(entry.entity_id)
