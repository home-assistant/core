"""UniFi Protect data migrations."""

from itertools import chain
import logging
from typing import TypedDict

from uiprotect import ProtectApiClient
from uiprotect.data import Bootstrap

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN
from .data import UFPConfigEntry

_LOGGER = logging.getLogger(__name__)


class EntityRef(TypedDict):
    """Entity ref parameter variable."""

    id: str
    platform: Platform


class EntityUsage(TypedDict):
    """Entity usages response variable."""

    automations: dict[str, list[str]]
    scripts: dict[str, list[str]]


@callback
def check_if_used(
    hass: HomeAssistant, entry: UFPConfigEntry, entities: dict[str, EntityRef]
) -> dict[str, EntityUsage]:
    """Check for usages of entities and return them."""

    entity_registry = er.async_get(hass)
    refs: dict[str, EntityUsage] = {
        ref: {"automations": {}, "scripts": {}} for ref in entities
    }

    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        for ref_id, ref in entities.items():
            if (
                entity.domain == ref["platform"]
                and entity.disabled_by is None
                and ref["id"] in entity.unique_id
            ):
                entity_automations = automations_with_entity(hass, entity.entity_id)
                entity_scripts = scripts_with_entity(hass, entity.entity_id)
                if entity_automations:
                    refs[ref_id]["automations"][entity.entity_id] = entity_automations
                if entity_scripts:
                    refs[ref_id]["scripts"][entity.entity_id] = entity_scripts

    return refs


@callback
def create_repair_if_used(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    breaks_in: str,
    entities: dict[str, EntityRef],
) -> None:
    """Create repairs for used entities that are deprecated."""

    usages = check_if_used(hass, entry, entities)
    for ref_id, refs in usages.items():
        issue_id = f"deprecate_{ref_id}"
        automations = refs["automations"]
        scripts = refs["scripts"]
        if automations or scripts:
            items = sorted(
                set(chain.from_iterable(chain(automations.values(), scripts.values())))
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                breaks_in_ha_version=breaks_in,
                severity=IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={
                    "items": "* `" + "`\n* `".join(items) + "`\n"
                },
            )
        else:
            _LOGGER.debug("No found usages of %s", ref_id)
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_migrate_data(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    protect: ProtectApiClient,
    bootstrap: Bootstrap,
) -> None:
    """Run all valid UniFi Protect data migrations."""

    _LOGGER.debug("Start Migrate: async_deprecate_hdr")
    async_deprecate_hdr(hass, entry)
    _LOGGER.debug("Completed Migrate: async_deprecate_hdr")

    _LOGGER.debug("Start Migrate: async_remove_aiport_devices")
    async_remove_aiport_devices(hass, entry)
    _LOGGER.debug("Completed Migrate: async_remove_aiport_devices")

    _LOGGER.debug("Start Migrate: async_migrate_insecure_cameras")
    async_migrate_insecure_cameras(hass, entry)
    _LOGGER.debug("Completed Migrate: async_migrate_insecure_cameras")

    _LOGGER.debug("Start Migrate: async_remove_package_binary_sensor")
    async_remove_package_binary_sensor(hass, entry)
    _LOGGER.debug("Completed Migrate: async_remove_package_binary_sensor")


# Device type (``ProtectAdoptableDeviceModel.type``) reported by AI Ports. Matched
# in the registry so cleanup does not depend on the bundled library still exposing
# the AI Port model.
_AIPORT_DEVICE_TYPE = "AI Port"


@callback
def async_remove_aiport_devices(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Remove AI Port devices and their diagnostic-only entities.

    AI Ports only ever exposed diagnostic sensors (no automation-relevant
    functionality) and behave transparently, extending the camera they back.
    They have no public API representation, so support is dropped. Devices are
    matched from the registry (by device type) rather than the live bootstrap, so
    cleanup works even once the library drops the AI Port model.

    Added in 2026.7.0
    """
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.model_id != _AIPORT_DEVICE_TYPE:
            continue
        device_registry.async_remove_device(device.id)


@callback
def async_migrate_insecure_cameras(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Migrate the legacy plain-RTSP "(insecure)" camera entities.

    Streams now come from the public API, which is RTSPS-only, so the old
    ``{mac}_{channel}_insecure`` camera entities no longer exist. Redirect each
    to its secure unique_id (``{mac}_{channel}``) so its history/customizations
    carry over to the public stream; if the secure entity already exists, drop
    the redundant insecure one (raising a repair first if it is still used).

    Added in 2026.7.0
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != Platform.CAMERA or not entity.unique_id.endswith(
            "_insecure"
        ):
            continue
        secure_unique_id = entity.unique_id.removesuffix("_insecure")
        secure_entity_id = registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, secure_unique_id
        )
        if secure_entity_id is None:
            registry.async_update_entity(
                entity.entity_id, new_unique_id=secure_unique_id
            )
            continue
        _async_repair_if_used(
            hass,
            entity,
            f"insecure_camera_removed_{entity.unique_id}",
            "insecure_camera_removed",
            {"replacement": secure_entity_id},
        )
        registry.async_remove(entity.entity_id)


@callback
def _async_repair_if_used(
    hass: HomeAssistant,
    entity: er.RegistryEntry,
    issue_id: str,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Raise a persistent repair before removing an entity that is still in use.

    Removal cannot rewrite the user's automations/scripts, so a persistent repair
    lists the affected ones (the caller supplies any replacement hint via
    ``placeholders``). Disabled entities are skipped: they are not active in any
    automation.
    """
    if entity.disabled_by is not None:
        return
    items = sorted(
        set(automations_with_entity(hass, entity.entity_id))
        | set(scripts_with_entity(hass, entity.entity_id))
    )
    if not items:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `" + "`\n* `".join(items) + "`\n",
            **(placeholders or {}),
        },
    )


@callback
def async_remove_package_binary_sensor(
    hass: HomeAssistant, entry: UFPConfigEntry
) -> None:
    """Remove the package smart-detect binary sensor.

    Package detection is a momentary smart-detect event, so it now surfaces as a
    package event entity instead of a sustained binary sensor. The old
    ``{mac}_smart_obj_package`` binary sensors no longer exist; remove each stale
    entry, raising a repair first if a still-enabled one is referenced by an
    automation or script.

    Added in 2026.7.0
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != Platform.BINARY_SENSOR or not entity.unique_id.endswith(
            "_smart_obj_package"
        ):
            continue
        _async_repair_if_used(
            hass,
            entity,
            f"package_binary_sensor_removed_{entity.unique_id}",
            "package_binary_sensor_removed",
        )
        registry.async_remove(entity.entity_id)


@callback
def async_deprecate_hdr(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Check for usages of hdr_mode switch and raise repair if it is used.

    UniFi Protect v3.0.22 changed how HDR works so it is
    no longer a simple on/off toggle. There is Always On,
    Always Off and Auto. So it has been migrated to a
    select. The old switch is now deprecated.

    Added in 2024.4.0
    """

    create_repair_if_used(
        hass,
        entry,
        "2024.10.0",
        {"hdr_switch": {"id": "hdr_mode", "platform": Platform.SWITCH}},
    )
