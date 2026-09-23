"""Take over an installation of the custom integration this replaces.

The config entry of a `custom_components/hacs` install is handed to this
integration by the loader, so the registry entries, devices and issues it left
behind are still filed under the `"hacs"` domain. They are adopted here on the
first setup after the upgrade.
"""

from pathlib import Path
import shutil
from urllib.parse import parse_qsl, urlencode

from homeassistant.components import lovelace
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util.json import json_loads_object

from .const import (
    DASHBOARD_RESOURCE_BASE,
    DOMAIN,
    LEGACY_DASHBOARD_RESOURCE_BASE,
    LEGACY_HACS_REPOSITORY_ID,
    LEGACY_HACS_SYSTEM_ID,
)
from .utils.logger import LOGGER
from .utils.storage import LEGACY_DATA_STORAGE_KEY, LEGACY_STORAGE_KEYS, get_storage_key

LEGACY_HACS_DOMAIN = "hacs"

# Options that only ever existed in the custom integration and have no
# meaning for the Marketplace.
DROPPED_OPTIONS = ("sidepanel_title", "sidepanel_icon", "experimental")


@callback
def async_adopt_legacy_install(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Adopt what the previous install left behind, if there is anything."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    legacy_entities = [
        entity for entity in entities if entity.platform == LEGACY_HACS_DOMAIN
    ]
    legacy_devices = [
        device
        for device in devices
        if any(domain == LEGACY_HACS_DOMAIN for domain, _ in device.identifiers)
    ]
    legacy_issues = [
        issue_id
        for domain, issue_id in ir.async_get(hass).issues
        if domain == LEGACY_HACS_DOMAIN
    ]
    dropped_options = [option for option in DROPPED_OPTIONS if option in entry.options]

    if (
        not legacy_entities
        and not legacy_devices
        and not legacy_issues
        and not dropped_options
    ):
        return

    _async_adopt_entities(entity_registry, entry, legacy_entities)
    _async_adopt_devices(entity_registry, device_registry, legacy_devices)

    for issue_id in legacy_issues:
        ir.async_delete_issue(hass, LEGACY_HACS_DOMAIN, issue_id)

    if dropped_options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                option: value
                for option, value in entry.options.items()
                if option not in DROPPED_OPTIONS
            },
        )

    LOGGER.info(
        "Took over the existing installation of %s entities and %s devices, "
        "%s repair issues removed",
        len(legacy_entities),
        len(legacy_devices),
        len(legacy_issues),
    )


@callback
def _async_adopt_entities(
    entity_registry: er.EntityRegistry,
    entry: ConfigEntry,
    legacy_entities: list[er.RegistryEntry],
) -> None:
    """Move the registry entries of the previous install to this integration."""
    for entity in legacy_entities:
        if taken := entity_registry.async_get_entity_id(
            entity.domain, DOMAIN, entity.unique_id
        ):
            LOGGER.debug(
                "Removing %s, %s already holds unique id %s",
                entity.entity_id,
                taken,
                entity.unique_id,
            )
            entity_registry.async_remove(entity.entity_id)
            continue

        entity_registry.async_update_entity_platform(
            entity.entity_id, DOMAIN, new_config_entry_id=entry.entry_id
        )


@callback
def _async_adopt_devices(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    legacy_devices: list[dr.DeviceEntry],
) -> None:
    """Rewrite the device identifiers to this integration."""
    for device in legacy_devices:
        if (LEGACY_HACS_DOMAIN, LEGACY_HACS_SYSTEM_ID) in device.identifiers:
            _async_remove_system_device(entity_registry, device_registry, device)
            continue

        adopted = {
            (DOMAIN, identifier)
            for domain, identifier in device.identifiers
            if domain == LEGACY_HACS_DOMAIN
        }
        kept = {
            (domain, identifier)
            for domain, identifier in device.identifiers
            if domain != LEGACY_HACS_DOMAIN
        }

        if existing := _async_find_device(device_registry, device, adopted):
            for entity in er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            ):
                entity_registry.async_update_entity(
                    entity.entity_id, device_id=existing.id
                )
            device_registry.async_remove_device(device.id)
            continue

        device_registry.async_update_device(device.id, new_identifiers=adopted | kept)


@callback
def _async_find_device(
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
    identifiers: set[tuple[str, str]],
) -> dr.DeviceEntry | None:
    """Return the device of this integration that claims one of the identifiers."""
    for identifier in identifiers:
        if (
            existing := device_registry.async_get_device_by_identifier(
                identifier, device.config_entry_id
            )
        ) is not None and existing.id != device.id:
            return existing

    return None


@callback
def _async_remove_system_device(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Remove the device of the previous install, the Marketplace is part of core."""
    for entity in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        if entity.unique_id == LEGACY_HACS_REPOSITORY_ID:
            entity_registry.async_remove(entity.entity_id)

    device_registry.async_remove_device(device.id)


async def async_remove_duplicate_entries(hass: HomeAssistant) -> None:
    """Keep a single config entry when two of them landed next to each other.

    Both integrations could be configured side by side, which leaves two entries
    once the `custom_components/hacs` one is handed over. The oldest one wins, so
    the entry the user has been using the longest keeps its registry entries.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) < 2:
        return

    kept, *duplicates = sorted(entries, key=lambda entry: entry.created_at)

    if not kept.data.get(CONF_TOKEN):
        token = next(
            (
                entry.data[CONF_TOKEN]
                for entry in duplicates
                if entry.data.get(CONF_TOKEN)
            ),
            None,
        )
        if token is not None:
            hass.config_entries.async_update_entry(
                kept, data={**kept.data, CONF_TOKEN: token}
            )

    for entry in duplicates:
        LOGGER.warning(
            "Removing duplicate configuration entry %s, %s is kept",
            entry.entry_id,
            kept.entry_id,
        )
        await hass.config_entries.async_remove(entry.entry_id)


def _migrated_resource_url(url: str) -> str:
    """Return the URL of a dashboard resource below the path we serve now."""
    path, _, query = url.partition("?")
    path = (
        f"{DASHBOARD_RESOURCE_BASE}{path.removeprefix(LEGACY_DASHBOARD_RESOURCE_BASE)}"
    )

    if not query:
        return path

    parameters = [
        ("v" if key == "hacstag" else key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
    ]

    return f"{path}?{urlencode(parameters)}"


async def async_migrate_dashboard_resources(hass: HomeAssistant) -> None:
    """Point the dashboard resources at the path the frontend serves.

    The Marketplace used to serve www/community itself, the frontend serves the very
    same directory as /local. Only a storage collection can be rewritten, a
    YAML one is the user's own file.
    """
    if (lovelace_data := hass.data.get(lovelace.LOVELACE_DATA)) is None:
        return

    resources = lovelace_data.resources
    if not isinstance(resources, lovelace.resources.ResourceStorageCollection):
        return

    if not resources.loaded:
        await resources.async_load()

    migrated = 0
    for item in list(resources.async_items()):
        if not item["url"].startswith(f"{LEGACY_DASHBOARD_RESOURCE_BASE}/"):
            continue

        await resources.async_update_item(
            item["id"], {"url": _migrated_resource_url(item["url"])}
        )
        migrated += 1

    if migrated:
        LOGGER.info(
            "Moved %s dashboard resource(s) to %s",
            migrated,
            DASHBOARD_RESOURCE_BASE,
        )


def _is_legacy_integration(directory: Path) -> bool:
    """Return if the directory holds the custom integration this replaces."""
    try:
        manifest = json_loads_object(
            (directory / "manifest.json").read_text(encoding="utf-8")
        )
    except OSError, ValueError:
        return False

    return manifest.get("domain") == LEGACY_HACS_DOMAIN


def _remove_legacy_files(config_path: str) -> list[str]:
    """Remove what the previous install left on disk, return what was removed.

    Nothing is touched before the Marketplace has its own repositories file, the
    legacy storage files are only gone once their data has been adopted.
    """
    storage_path = Path(config_path, STORAGE_DIR)
    if not (storage_path / get_storage_key("repositories")).is_file():
        return []

    removed: list[str] = []

    integration_path = Path(config_path, "custom_components", LEGACY_HACS_DOMAIN)
    if _is_legacy_integration(integration_path):
        try:
            shutil.rmtree(integration_path)
        except OSError as exception:
            LOGGER.warning("Could not remove %s: %s", integration_path, exception)
        else:
            removed.append(str(integration_path))

    legacy_files = {
        legacy_key: get_storage_key(key)
        for key, legacy_key in LEGACY_STORAGE_KEYS.items()
    }
    legacy_files[LEGACY_DATA_STORAGE_KEY] = get_storage_key("repositories")

    for legacy_key, storage_key in legacy_files.items():
        legacy_path = storage_path / legacy_key
        if not legacy_path.is_file() or not (storage_path / storage_key).is_file():
            continue

        try:
            legacy_path.unlink()
        except OSError as exception:
            LOGGER.warning("Could not remove %s: %s", legacy_path, exception)
        else:
            removed.append(str(legacy_path))

    return removed


async def async_remove_legacy_files(hass: HomeAssistant) -> None:
    """Clean up the files of the previous install once the Marketplace adopted them."""
    if removed := await hass.async_add_executor_job(
        _remove_legacy_files, hass.config.path()
    ):
        LOGGER.info(
            "Removed what the previous installation left behind: %s",
            ", ".join(removed),
        )
