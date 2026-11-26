"""UniFi Protect data migrations."""

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, NamedTuple

from uiprotect.data import ModelType, ProtectAdoptableDeviceModel
from uiprotect.data.public_devices import PublicDeviceModel

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
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .data import UFPConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_migrate_data(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Run all valid UniFi Protect data migrations.

    Every migration operates purely on the entity/device registries, so this
    runs in both connection modes (no bootstrap required).
    """

    _LOGGER.debug("Start Migrate: async_remove_hdr_switch")
    async_remove_hdr_switch(hass, entry)
    _LOGGER.debug("Completed Migrate: async_remove_hdr_switch")

    _LOGGER.debug("Start Migrate: async_remove_aiport_devices")
    async_remove_aiport_devices(hass, entry)
    _LOGGER.debug("Completed Migrate: async_remove_aiport_devices")

    _LOGGER.debug("Start Migrate: async_migrate_insecure_cameras")
    async_migrate_insecure_cameras(hass, entry)
    _LOGGER.debug("Completed Migrate: async_migrate_insecure_cameras")

    _LOGGER.debug("Start Migrate: async_remove_package_binary_sensor")
    async_remove_package_binary_sensor(hass, entry)
    _LOGGER.debug("Completed Migrate: async_remove_package_binary_sensor")

    _LOGGER.debug("Start Migrate: async_migrate_sensor_signal_strength")
    async_migrate_sensor_signal_strength(hass, entry)
    _LOGGER.debug("Completed Migrate: async_migrate_sensor_signal_strength")

    _LOGGER.debug("Start Migrate: async_link_removal_repairs")
    async_link_removal_repairs(hass, entry)
    _LOGGER.debug("Completed Migrate: async_link_removal_repairs")


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
    # The rename must land before the camera platform sets up. Only the removal waits.
    removals: list[_Removal] = []
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
        removals.append(
            _Removal(
                entity.domain,
                entity.unique_id,
                f"insecure_camera_removed_{entity.unique_id}",
                "insecure_camera_removed",
                {"replacement": secure_entity_id},
            )
        )
    _async_remove_when_started(hass, entry, removals)


# Persistent removal repairs, keyed by their issue id prefix up to
# ``_removed_`` and pointing at the platforms the removed entity was on.
_REMOVAL_REPAIR_PLATFORMS: dict[str, tuple[Platform, ...]] = {
    "insecure_camera": (Platform.CAMERA,),
    "package_binary_sensor": (Platform.BINARY_SENSOR,),
    "hdr_switch": (Platform.SWITCH,),
    "sense_setting_mirror": (Platform.BINARY_SENSOR, Platform.SENSOR),
}


@callback
def async_link_removal_repairs(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Link the removal repairs raised before they named their config entry.

    Their entity is gone, so they are never raised again. The deleted entity
    registry entry of the removed entity still names the entry that owned it;
    repairs of entities this entry did not own are left alone. Re-raising the
    repair keeps its ignored state.

    Added in 2026.12.0
    """
    owned = {
        (deleted.domain, deleted.unique_id)
        for deleted in er.async_get(hass).deleted_entities.values()
        if deleted.platform == DOMAIN and deleted.config_entry_id == entry.entry_id
    }
    for (domain, issue_id), issue in list(ir.async_get(hass).issues.items()):
        prefix, _, unique_id = issue_id.partition("_removed_")
        if (
            domain != DOMAIN
            or not issue.is_persistent
            or issue.config_entry_id is not None
            or not any(
                (platform, unique_id) in owned
                for platform in _REMOVAL_REPAIR_PLATFORMS.get(prefix, ())
            )
        ):
            continue
        if TYPE_CHECKING:
            assert issue.translation_key is not None
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=True,
            config_entry_id=entry.entry_id,
            severity=IssueSeverity.WARNING,
            translation_key=issue.translation_key,
            translation_placeholders=issue.translation_placeholders,
        )


@callback
def _async_repair_if_used(
    hass: HomeAssistant,
    entity: er.RegistryEntry,
    issue_id: str,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Raise a repair for an entity that is going away and is still in use.

    A removal cannot rewrite the user's automations/scripts, so the repair
    lists the affected ones (the caller supplies any replacement hint via
    ``placeholders``). Disabled entities are skipped: they are not active in
    any automation.
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
        config_entry_id=entity.config_entry_id,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `" + "`\n* `".join(items) + "`\n",
            **(placeholders or {}),
        },
    )


class _Removal(NamedTuple):
    """An entity to remove once startup is done, with the repair if it is used."""

    domain: str
    unique_id: str
    issue_id: str
    translation_key: str
    placeholders: dict[str, str] | None = None


@callback
def _async_remove_when_started(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    removals: list[_Removal],
) -> None:
    """Remove entities once startup is done, raising a repair for used ones.

    Before the automations are loaded every entity looks unused, so removing
    earlier would drop the repair for good.
    """
    if not removals:
        return

    @callback
    def _async_remove(_hass: HomeAssistant) -> None:
        registry = er.async_get(hass)
        for removal in removals:
            entity_id = registry.async_get_entity_id(
                removal.domain, DOMAIN, removal.unique_id
            )
            if entity_id is None or (entity := registry.async_get(entity_id)) is None:
                continue
            _async_repair_if_used(
                hass,
                entity,
                removal.issue_id,
                removal.translation_key,
                removal.placeholders,
            )
            registry.async_remove(entity_id)

    entry.async_on_unload(async_at_started(hass, _async_remove))


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
    removals: list[_Removal] = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != Platform.BINARY_SENSOR or not entity.unique_id.endswith(
            "_smart_obj_package"
        ):
            continue
        removals.append(
            _Removal(
                entity.domain,
                entity.unique_id,
                f"package_binary_sensor_removed_{entity.unique_id}",
                "package_binary_sensor_removed",
            )
        )
    _async_remove_when_started(hass, entry, removals)


@callback
def async_remove_hdr_switch(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Remove the HDR mode switch.

    The switch could not represent the auto HDR mode, so it was deprecated in
    2024.4.0 in favor of the HDR mode select. Remove each stale ``{mac}_hdr_mode``
    switch, raising a repair first if a still-enabled one is referenced by an
    automation or script.

    Added in 2026.11.0
    """
    # Drop the stored record of the old deprecation repair.
    ir.async_delete_issue(hass, DOMAIN, "deprecate_hdr_switch")
    registry = er.async_get(hass)
    removals: list[_Removal] = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != Platform.SWITCH or not entity.unique_id.endswith(
            "_hdr_mode"
        ):
            continue
        removals.append(
            _Removal(
                entity.domain,
                entity.unique_id,
                f"hdr_switch_removed_{entity.unique_id}",
                "hdr_switch_removed",
            )
        )
    _async_remove_when_started(hass, entry, removals)


@callback
def async_migrate_sensor_signal_strength(
    hass: HomeAssistant, entry: UFPConfigEntry
) -> None:
    """Rename the ``{mac}_ble_signal`` unique_id to ``{mac}_signal_strength``.

    Renamed because sensors connect over Bluetooth or SuperLink. The entity keeps
    its history and customizations. If the new entity already exists (after a
    downgrade and upgrade), the old one is dropped.

    Added in 2026.11.0
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain != Platform.SENSOR or not entity.unique_id.endswith(
            "_ble_signal"
        ):
            continue
        mac = entity.unique_id.removesuffix("_ble_signal")
        new_unique_id = f"{mac}_signal_strength"
        if registry.async_get_entity_id(Platform.SENSOR, DOMAIN, new_unique_id):
            registry.async_remove(entity.entity_id)
            continue
        registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)


# Removed read-only mirrors of the sense setting controls, keyed by the mirror's
# (platform, key) and pointing at the (platform, key) of the control that
# replaces it. Camera and light entities reuse these keys, so the match is
# scoped to sensor MACs.
_SENSE_SETTING_MIRRORS: dict[tuple[str, str], tuple[Platform, str]] = {
    (Platform.BINARY_SENSOR, "motion_enabled"): (Platform.SWITCH, "motion"),
    (Platform.BINARY_SENSOR, "temperature"): (Platform.SWITCH, "temperature"),
    (Platform.BINARY_SENSOR, "humidity"): (Platform.SWITCH, "humidity"),
    (Platform.BINARY_SENSOR, "light"): (Platform.SWITCH, "light"),
    (Platform.BINARY_SENSOR, "alarm"): (Platform.SWITCH, "alarm"),
    (Platform.SENSOR, "sensitivity"): (Platform.NUMBER, "sensitivity"),
}


@callback
def async_remove_sense_setting_mirrors(
    hass: HomeAssistant, entry: UFPConfigEntry, sensor_macs: set[str]
) -> None:
    """Remove the read-only mirrors of the sense setting controls.

    Deprecated in 2026.9.0: the switch or number they mirror writes through the
    public API and is available to every user. Remove each stale entry, raising
    a repair first if a still-enabled one is referenced by an automation or
    script, and drop the stored deprecation repair.

    Runs after platform setup, unlike the other migrations in this file: the
    repair names the replacement, which only exists once the platform is set up.

    Added in 2026.11.0
    """
    if not sensor_macs:
        return
    registry = er.async_get(hass)
    removals: list[_Removal] = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        mac, _, key = entity.unique_id.partition("_")
        replacement = _SENSE_SETTING_MIRRORS.get((entity.domain, key))
        if replacement is None or mac not in sensor_macs:
            continue
        ir.async_delete_issue(
            hass, DOMAIN, f"sense_setting_mirror_deprecated_{entity.unique_id}"
        )
        replacement_platform, replacement_key = replacement
        issue_id = f"sense_setting_mirror_removed_{entity.unique_id}"
        if replacement_entity_id := registry.async_get_entity_id(
            replacement_platform, DOMAIN, f"{mac}_{replacement_key}"
        ):
            removals.append(
                _Removal(
                    entity.domain,
                    entity.unique_id,
                    issue_id,
                    "sense_setting_mirror_removed",
                    {"replacement": replacement_entity_id},
                )
            )
        else:
            removals.append(
                _Removal(
                    entity.domain,
                    entity.unique_id,
                    issue_id,
                    "sense_setting_mirror_removed_no_replacement",
                )
            )
    _async_remove_when_started(hass, entry, removals)


# Removed read-only mirrors and private API sensors, keyed by device model and
# then by their own (platform, key), pointing at the (platform, key) of the
# public entity that replaces them and the repair text. A ``None`` replacement
# key is the device entity itself, whose unique_id is the bare MAC. Scoped by
# model because other devices reuse the keys.
type _Replacements = dict[tuple[str, str], tuple[Platform, str | None, str]]

_REPLACED_ENTITIES: dict[ModelType, _Replacements] = {
    ModelType.LIGHT: {
        (Platform.BINARY_SENSOR, "light"): (
            Platform.LIGHT,
            None,
            "setting_mirror_removed",
        ),
        (Platform.BINARY_SENSOR, "status_light"): (
            Platform.SWITCH,
            "status_light",
            "setting_mirror_removed",
        ),
        (Platform.SENSOR, "sensitivity"): (
            Platform.NUMBER,
            "sensitivity",
            "setting_mirror_removed",
        ),
        # The sensor showed the raw mode, the select its own option names.
        (Platform.SENSOR, "light_motion"): (
            Platform.SELECT,
            "light_motion",
            "setting_mirror_removed_light_mode",
        ),
    },
    ModelType.CAMERA: {
        **{
            (Platform.BINARY_SENSOR, key): (
                Platform.SWITCH,
                key,
                "setting_mirror_removed",
            )
            for key in (
                "status_light",
                "high_fps",
                "osd_name",
                "osd_date",
                "osd_logo",
                "osd_bitrate",
                "smart_person",
                "smart_vehicle",
                "smart_animal",
                "smart_package",
                "smart_licenseplate",
                "smart_smoke",
                "smart_cmonx",
                "smart_siren",
                "smart_baby_cry",
                "smart_speak",
                "smart_bark",
                "smart_car_alarm",
                "smart_car_horn",
                "smart_glass_break",
            )
        },
        # The binary sensor was on for both HDR modes the select tells apart.
        (Platform.BINARY_SENSOR, "hdr_mode"): (
            Platform.SELECT,
            "hdr_mode",
            "setting_mirror_removed_hdr_mode",
        ),
        # The number is unavailable while the microphone is disabled.
        (Platform.SENSOR, "mic_level"): (
            Platform.NUMBER,
            "mic_level",
            "setting_mirror_removed_mic_level",
        ),
        # The text entity falls back to the default message where the sensor
        # was empty.
        (Platform.SENSOR, "doorbell_text"): (
            Platform.TEXT,
            "doorbell",
            "setting_mirror_removed_doorbell_text",
        ),
        (Platform.BINARY_SENSOR, "doorbell"): (
            Platform.EVENT,
            "doorbell",
            "doorbell_sensor_removed",
        ),
        (Platform.SENSOR, "doorbell_last_trip_time"): (
            Platform.EVENT,
            "doorbell",
            "last_event_sensor_removed",
        ),
        (Platform.SENSOR, "motion_last_trip_time"): (
            Platform.EVENT,
            "motion_detection",
            "last_event_sensor_removed",
        ),
    },
}

# Removed device setup and device data entities that only the private API
# provided, keyed by device model and then by (platform, key).
_PRIVATE_ONLY_ENTITIES: dict[ModelType, frozenset[tuple[Platform, str]]] = {
    ModelType.CAMERA: frozenset(
        {
            (Platform.SWITCH, "ssh"),
            (Platform.BINARY_SENSOR, "ssh"),
            (Platform.SENSOR, "lens_type"),
            (Platform.SENSOR, "voltage"),
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "phy_rate"),
            (Platform.SENSOR, "oldest_recording"),
            (Platform.SENSOR, "storage_used"),
            (Platform.SENSOR, "write_rate"),
            (Platform.SENSOR, "stats_rx"),
            (Platform.SENSOR, "stats_tx"),
        }
    ),
    ModelType.LIGHT: frozenset(
        {
            (Platform.SWITCH, "ssh"),
            (Platform.BINARY_SENSOR, "ssh"),
            (Platform.SELECT, "paired_camera"),
            (Platform.SENSOR, "paired_camera"),
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "phy_rate"),
        }
    ),
    ModelType.VIEWPORT: frozenset(
        {
            (Platform.SWITCH, "ssh"),
            (Platform.BINARY_SENSOR, "ssh"),
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "phy_rate"),
        }
    ),
    ModelType.SENSOR: frozenset(
        {
            (Platform.SELECT, "mount_type"),
            (Platform.SENSOR, "mount_type"),
            (Platform.SELECT, "paired_camera"),
            (Platform.SENSOR, "paired_camera"),
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "phy_rate"),
        }
    ),
    ModelType.CHIME: frozenset(
        {
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "phy_rate"),
        }
    ),
    ModelType.NVR: frozenset(
        {
            (Platform.SWITCH, "analytics_enabled"),
            (Platform.SWITCH, "insights_enabled"),
            (Platform.SENSOR, "uptime"),
            (Platform.SENSOR, "cpu_utilization"),
            (Platform.SENSOR, "cpu_temperature"),
            (Platform.SENSOR, "memory_utilization"),
        }
    ),
}


@callback
def async_remove_private_api_entities(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    nvr_mac: str,
    devices: dict[ModelType, Iterable[ProtectAdoptableDeviceModel | PublicDeviceModel]],
) -> None:
    """Remove the read-only mirrors and the private API only entities.

    Deprecated in 2026.11.0: the mirrors and the camera ring and motion sensors
    are replaced by public API entities, and the official API does not provide
    the other entities. Remove each stale entry, raising a repair first if a still-enabled one is
    referenced by an automation or script, and drop the deprecation repair.

    Runs after platform setup, like ``async_remove_sense_setting_mirrors``, so
    the repair can name the replacement.

    Added in 2027.1.0
    """
    models = {nvr_mac: ModelType.NVR}
    for device_model, model_devices in devices.items():
        models.update(
            dict.fromkeys((device.mac for device in model_devices), device_model)
        )
    registry = er.async_get(hass)
    removals: list[_Removal] = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        mac, _, key = entity.unique_id.partition("_")
        if (model := models.get(mac)) is None:
            continue
        platform_key = (entity.domain, key)
        replacement = _REPLACED_ENTITIES.get(model, {}).get(platform_key)
        if replacement is None and platform_key not in _PRIVATE_ONLY_ENTITIES.get(
            model, frozenset()
        ):
            continue
        ir.async_delete_issue(
            hass, DOMAIN, f"setting_mirror_deprecated_{entity.unique_id}"
        )
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"private_only_entity_deprecated_{entity.domain}_{entity.unique_id}",
        )
        translation_key = "private_api_entity_removed"
        placeholders: dict[str, str] | None = None
        if replacement is not None:
            platform, replacement_key, replacement_translation_key = replacement
            if replacement_entity_id := registry.async_get_entity_id(
                platform,
                DOMAIN,
                mac if replacement_key is None else f"{mac}_{replacement_key}",
            ):
                translation_key = replacement_translation_key
                placeholders = {"replacement": replacement_entity_id}
        removals.append(
            _Removal(
                entity.domain,
                entity.unique_id,
                # SSH, mount type and paired camera share a unique_id across
                # two platforms.
                f"private_api_entity_removed_{entity.domain}_{entity.unique_id}",
                translation_key,
                placeholders,
            )
        )
    _async_remove_when_started(hass, entry, removals)
