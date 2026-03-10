"""The jvc_projector integration."""

from __future__ import annotations

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorTimeoutError

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
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
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

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
    create_deprecated_sensor_issues(hass, entry, coordinator)

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

    @callback
    def _update_entry(entry: RegistryEntry) -> dict[str, str] | None:
        """Fix unique_id of power binary_sensor entry."""
        if entry.domain == Platform.BINARY_SENSOR and ":" not in entry.unique_id:
            if entry.unique_id.endswith("_power"):
                return {"new_unique_id": f"{coordinator.unique_id}_power"}
        return None

    await async_migrate_entries(hass, config_entry.entry_id, _update_entry)


def create_deprecated_sensor_issues(
    hass: HomeAssistant,
    config_entry: JVCConfigEntry,
    coordinator: JvcProjectorDataUpdateCoordinator,
) -> None:
    """Create deprecation issues for legacy sensors."""
    entity_registry = er.async_get(hass)

    for key in ("hdr_processing", "picture_mode"):
        issue_id = f"deprecated_sensor_{config_entry.entry_id}_{key}"
        unique_id = f"{coordinator.unique_id}_{key}"
        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, unique_id
        )

        if entity_id is None:
            async_delete_issue(hass, DOMAIN, issue_id)
            continue

        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is None:
            async_delete_issue(hass, DOMAIN, issue_id)
            continue

        items = _get_automations_and_scripts_using_entity(hass, entity_id)
        if entity_entry.disabled and not items:
            entity_registry.async_remove(entity_id)
            async_delete_issue(hass, DOMAIN, issue_id)
            continue

        placeholders = {
            "entity_id": entity_id,
            "entity_name": (
                entity_entry.name or entity_entry.original_name or "Unknown"
            ),
            "replacement_entity_id": (
                entity_registry.async_get_entity_id(Platform.SELECT, DOMAIN, unique_id)
                or "select.unknown"
            ),
        }

        translation_key = "deprecated_sensor"
        if items:
            translation_key = "deprecated_sensor_scripts"
            placeholders["items"] = "\n".join(items)

        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )


def _get_automations_and_scripts_using_entity(
    hass: HomeAssistant, entity_id: str
) -> list[str]:
    """Get automations and scripts using an entity."""
    automations = automations_with_entity(hass, entity_id)
    scripts = scripts_with_entity(hass, entity_id)
    if not automations and not scripts:
        return []

    entity_registry = er.async_get(hass)
    return [
        f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
        for integration, entities in (
            ("automation", automations),
            ("script", scripts),
        )
        for used_entity_id in entities
        if (item := entity_registry.async_get(used_entity_id))
    ]
