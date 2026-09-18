"""Take over an installation of the custom integration this replaces.

The config entry of a `custom_components/hacs` install is handed to this
integration by the loader, so the registry entries, devices and issues it left
behind are still filed under the `"hacs"` domain. They are adopted here on the
first setup after the upgrade.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .const import DOMAIN, LEGACY_HACS_REPOSITORY_ID, LEGACY_HACS_SYSTEM_ID
from .utils.logger import LOGGER

LEGACY_HACS_DOMAIN = "hacs"

# Options that only ever existed in the custom integration and have no
# meaning for the store.
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
    """Remove the device of the previous install, the store is part of core."""
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
