"""Take over an installation of the custom integration this replaces.

The config entry of a `custom_components/hacs` install is handed to this
integration by the loader, so the registry entries, devices and issues it left
behind are still filed under the `"hacs"` domain. They are adopted here on the
first setup after the upgrade.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import parse_qsl, urlencode

from homeassistant.components import lovelace
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from .const import (
    CONF_WARNING_ACCEPTED,
    DASHBOARD_RESOURCE_BASE,
    DOMAIN,
    LEGACY_DASHBOARD_RESOURCE_BASE,
    LEGACY_HACS_REPOSITORY_ID,
    LEGACY_HACS_SYSTEM_ID,
)
from .utils.logger import LOGGER
from .utils.storage import LEGACY_STORAGE_KEYS, get_storage_key

LEGACY_HACS_DOMAIN = "hacs"

# Older releases of the custom integration wrote this file, nothing reads it.
LEGACY_HACS_DATA_FILE = "hacs.data"

YAML_RESOURCES_ISSUE_ID = "legacy_dashboard_resources"


@dataclass(frozen=True, slots=True)
class RetiredCategory:
    """A category the Marketplace no longer manages."""

    name: str
    issue_id: str
    placeholder: str


# These were once categories, the stored data can still hold them. What was
# downloaded stays in place and keeps running, only the Marketplace lets go.
RETIRED_CATEGORIES: dict[str, RetiredCategory] = {
    "appdaemon": RetiredCategory("AppDaemon", "appdaemon_not_supported", "apps"),
    "python_script": RetiredCategory(
        "python_script", "python_scripts_not_supported", "scripts"
    ),
}


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

    if (
        not legacy_entities
        and not legacy_devices
        and not legacy_issues
        and not entry.options
    ):
        return

    _async_adopt_entities(entity_registry, entry, legacy_entities)
    _async_adopt_devices(entity_registry, device_registry, legacy_devices)

    for issue_id in legacy_issues:
        ir.async_delete_issue(hass, LEGACY_HACS_DOMAIN, issue_id)

    # The Marketplace has no options, anything stored there is left from before
    if entry.options:
        hass.config_entries.async_update_entry(entry, options={})

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


def _display_name(repository_data: dict[str, Any]) -> str:
    """Return the name of a stored repository the way the panel showed it."""
    manifest = (
        repository_data.get("manifest")
        or repository_data.get("repository_manifest")
        or {}
    )
    if name := manifest.get("name"):
        return str(name)

    full_name: str = repository_data["full_name"]
    return (
        full_name.rsplit("/", maxsplit=1)[-1]
        .replace("-", " ")
        .replace("_", " ")
        .title()
    )


@callback
def async_forget_retired_repositories(
    hass: HomeAssistant, entry: ConfigEntry, repositories: dict[str, dict[str, Any]]
) -> None:
    """Forget the stored repositories of categories the Marketplace no longer has.

    Their files stay in place, whatever ran them keeps running them. Once they
    are gone from the dict, the next write drops them from the stored data too.
    """
    for category, retired in RETIRED_CATEGORIES.items():
        _async_forget_category(hass, entry, repositories, category, retired)


@callback
def _async_forget_category(
    hass: HomeAssistant,
    entry: ConfigEntry,
    repositories: dict[str, dict[str, Any]],
    category: str,
    retired: RetiredCategory,
) -> None:
    """Forget the stored repositories of one retired category."""
    forgotten = {
        repository_id: repositories.pop(repository_id)
        for repository_id, repository_data in list(repositories.items())
        if repository_data.get("category") == category
    }
    if not forgotten:
        return

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for repository_id in forgotten:
        for platform in (Platform.SWITCH, Platform.UPDATE):
            if entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, str(repository_id)
            ):
                entity_registry.async_remove(entity_id)

        if device := device_registry.async_get_device_by_identifier(
            (DOMAIN, str(repository_id)), entry.entry_id
        ):
            device_registry.async_remove_device(device.id)

    installed = sorted(
        _display_name(repository_data)
        for repository_data in forgotten.values()
        if repository_data.get("installed")
    )

    LOGGER.info(
        "Forgot %s %s repositories, %s of them downloaded",
        len(forgotten),
        retired.name,
        len(installed),
    )

    if not installed:
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        retired.issue_id,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=retired.issue_id,
        translation_placeholders={retired.placeholder: ", ".join(installed)},
    )


async def async_remove_duplicate_entries(hass: HomeAssistant) -> None:
    """Keep a single config entry when two of them landed next to each other.

    Both integrations could be configured side by side, which leaves two entries
    once the `custom_components/hacs` one is handed over. The entry that still
    owns entities of the custom integration wins, those are what the user works
    with today, and a removed entry takes its registry entries along. Otherwise
    the oldest one wins.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) < 2:
        return

    entity_registry = er.async_get(hass)

    def owns_legacy_entities(entry: ConfigEntry) -> bool:
        return any(
            entity.platform == LEGACY_HACS_DOMAIN
            for entity in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
        )

    kept, *duplicates = sorted(
        entries,
        key=lambda entry: (not owns_legacy_entities(entry), entry.created_at),
    )
    data = dict(kept.data)

    if not data.get(CONF_TOKEN):
        token = next(
            (
                entry.data[CONF_TOKEN]
                for entry in duplicates
                if entry.data.get(CONF_TOKEN)
            ),
            None,
        )
        if token is not None:
            data[CONF_TOKEN] = token

    # A user only has to read the warning once, whichever entry was there to
    # read it. Sorted oldest first, so the newest acceptance of a user wins.
    acceptances = sorted(
        (
            (user_id, acceptance)
            for entry in (kept, *duplicates)
            for user_id, acceptance in entry.data.get(CONF_WARNING_ACCEPTED, {}).items()
        ),
        key=lambda item: dt_util.parse_datetime(
            item[1]["accepted_at"], raise_on_error=True
        ),
    )
    if acceptances:
        data[CONF_WARNING_ACCEPTED] = dict(acceptances)

    if data != kept.data:
        hass.config_entries.async_update_entry(kept, data=data)

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

    The custom integration served www/community itself, the frontend serves the
    very same directory as /local. Only a storage collection can be rewritten, a
    YAML one is the user's own file: a repair issue tells what to change there.
    """
    if (lovelace_data := hass.data.get(lovelace.LOVELACE_DATA)) is None:
        return

    resources = lovelace_data.resources
    if not isinstance(resources, lovelace.resources.ResourceStorageCollection):
        _async_update_yaml_resources_issue(hass, resources.async_items())
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


@callback
def _async_update_yaml_resources_issue(
    hass: HomeAssistant, resources: list[dict[str, Any]]
) -> None:
    """Ask to update the YAML resources that still use the old path."""
    legacy_urls = [
        resource["url"]
        for resource in resources
        if resource["url"].startswith(f"{LEGACY_DASHBOARD_RESOURCE_BASE}/")
    ]

    if not legacy_urls:
        ir.async_delete_issue(hass, DOMAIN, YAML_RESOURCES_ISSUE_ID)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        YAML_RESOURCES_ISSUE_ID,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=YAML_RESOURCES_ISSUE_ID,
        translation_placeholders={
            "resources": "\n".join(
                f"- `{url}` becomes `{_migrated_resource_url(url)}`"
                for url in legacy_urls
            ),
        },
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
    legacy_files[LEGACY_HACS_DATA_FILE] = get_storage_key("repositories")

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
