"""Take over an installation of the HACS custom integration.

The config entry of a HACS install is handed to this integration by the loader,
so the registry entries, devices and issues it left behind are still filed under
the `hacs` domain. They are adopted here on the first setup after the upgrade.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .const import DOMAIN, HACS_REPOSITORY_ID, HACS_SYSTEM_ID
from .utils.logger import LOGGER

HACS_DOMAIN = "hacs"

# Options that only ever existed in HACS and have no meaning for the store.
DROPPED_OPTIONS = ("sidepanel_title", "sidepanel_icon", "experimental")


@callback
def async_migrate_from_hacs(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Adopt what a HACS install left behind, if there is anything to adopt."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    hacs_entities = [entity for entity in entities if entity.platform == HACS_DOMAIN]
    hacs_devices = [
        device
        for device in devices
        if any(domain == HACS_DOMAIN for domain, _ in device.identifiers)
    ]
    hacs_issues = [
        issue_id
        for domain, issue_id in ir.async_get(hass).issues
        if domain == HACS_DOMAIN
    ]
    dropped_options = [option for option in DROPPED_OPTIONS if option in entry.options]

    if (
        not hacs_entities
        and not hacs_devices
        and not hacs_issues
        and not dropped_options
    ):
        return

    _async_adopt_entities(entity_registry, entry, hacs_entities)
    _async_adopt_devices(entity_registry, device_registry, hacs_devices)

    for issue_id in hacs_issues:
        ir.async_delete_issue(hass, HACS_DOMAIN, issue_id)

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
        "Took over the existing HACS installation of %s entities and %s devices, "
        "%s repair issues removed",
        len(hacs_entities),
        len(hacs_devices),
        len(hacs_issues),
    )


@callback
def _async_adopt_entities(
    entity_registry: er.EntityRegistry,
    entry: ConfigEntry,
    hacs_entities: list[er.RegistryEntry],
) -> None:
    """Move the registry entries of HACS over to this integration."""
    for entity in hacs_entities:
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
    hacs_devices: list[dr.DeviceEntry],
) -> None:
    """Rewrite the identifiers of the HACS devices to this integration."""
    for device in hacs_devices:
        if (HACS_DOMAIN, HACS_SYSTEM_ID) in device.identifiers:
            _async_remove_system_device(entity_registry, device_registry, device)
            continue

        adopted = {
            (DOMAIN, identifier)
            for domain, identifier in device.identifiers
            if domain == HACS_DOMAIN
        }
        kept = {
            (domain, identifier)
            for domain, identifier in device.identifiers
            if domain != HACS_DOMAIN
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
    """Remove the HACS device, the store does not manage itself."""
    for entity in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        if entity.unique_id == HACS_REPOSITORY_ID:
            entity_registry.async_remove(entity.entity_id)

    device_registry.async_remove_device(device.id)


async def async_remove_duplicate_entries(hass: HomeAssistant) -> None:
    """Keep a single config entry when a HACS entry landed next to a store one.

    Both integrations could be configured side by side, which leaves two entries
    once the HACS one is handed over. The oldest one wins, so the entry the user
    has been using the longest keeps its registry entries.
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
