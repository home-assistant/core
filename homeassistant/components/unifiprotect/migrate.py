"""UniFi Protect data migrations."""

import logging
from typing import NamedTuple

from uiprotect.data import Bootstrap, ModelType

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


@callback
def _async_repair_if_used(
    hass: HomeAssistant,
    entity: er.RegistryEntry,
    issue_id: str,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
    breaks_in: str | None = None,
) -> None:
    """Raise a repair for an entity that is going away and is still in use.

    Neither a removal nor a deprecation can rewrite the user's
    automations/scripts, so the repair lists the affected ones (the caller
    supplies any replacement hint via ``placeholders``). Disabled entities are
    skipped: they are not active in any automation. Pass ``breaks_in`` while the
    entity still exists; the repair then clears itself once the last usage is
    gone, where a removal repair has to persist.
    """
    if entity.disabled_by is not None:
        return
    items = sorted(
        set(automations_with_entity(hass, entity.entity_id))
        | set(scripts_with_entity(hass, entity.entity_id))
    )
    if not items:
        if breaks_in is not None:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=breaks_in is None,
        breaks_in_ha_version=breaks_in,
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


# Release that removes the deprecated light mirrors.
LIGHT_SETTING_MIRROR_BREAKS_IN = "2027.1.0"

# Mirrors keyed by their own (platform, key), pointing at the (platform, key) of
# the control that replaces them and the repair text. A ``None`` replacement
# key is the device entity itself, whose unique_id is the bare MAC.
type _MirrorReplacements = dict[tuple[str, str], tuple[Platform, str | None, str]]

_LIGHT_MIRROR_REPLACEMENTS: _MirrorReplacements = {
    (Platform.BINARY_SENSOR, "light"): (
        Platform.LIGHT,
        None,
        "setting_mirror_deprecated",
    ),
    (Platform.BINARY_SENSOR, "status_light"): (
        Platform.SWITCH,
        "status_light",
        "setting_mirror_deprecated",
    ),
    (Platform.SENSOR, "sensitivity"): (
        Platform.NUMBER,
        "sensitivity",
        "setting_mirror_deprecated",
    ),
    # The sensor shows the raw mode, the select its own option names.
    (Platform.SENSOR, "light_motion"): (
        Platform.SELECT,
        "light_motion",
        "setting_mirror_deprecated_light_mode",
    ),
}


@callback
def async_deprecate_light_setting_mirrors(
    hass: HomeAssistant, entry: UFPConfigEntry, bootstrap: Bootstrap
) -> None:
    """Deprecate the read-only mirrors of the light controls.

    The light and its controls write through the public API, which the local
    user's write permission does not gate, so they are now available to every
    user and the ``PermRequired.NO_WRITE`` mirrors only duplicate them.

    Runs after platform setup so the repair can name the replacement.

    Added in 2026.11.0
    """
    _async_deprecate_setting_mirrors(
        hass,
        entry,
        {light.mac for light in bootstrap.lights.values()},
        _LIGHT_MIRROR_REPLACEMENTS,
        LIGHT_SETTING_MIRROR_BREAKS_IN,
    )


# Release that removes the deprecated camera mirrors.
CAMERA_SETTING_MIRROR_BREAKS_IN = "2027.1.0"

_CAMERA_MIRROR_REPLACEMENTS: _MirrorReplacements = {
    **{
        (Platform.BINARY_SENSOR, key): (
            Platform.SWITCH,
            key,
            "setting_mirror_deprecated",
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
    # The binary sensor is on for both HDR modes the select tells apart.
    (Platform.BINARY_SENSOR, "hdr_mode"): (
        Platform.SELECT,
        "hdr_mode",
        "setting_mirror_deprecated_hdr_mode",
    ),
    # The number is unavailable while the microphone is disabled.
    (Platform.SENSOR, "mic_level"): (
        Platform.NUMBER,
        "mic_level",
        "setting_mirror_deprecated_mic_level",
    ),
    # The text entity falls back to the default message where the sensor is empty.
    (Platform.SENSOR, "doorbell_text"): (
        Platform.TEXT,
        "doorbell",
        "setting_mirror_deprecated_doorbell_text",
    ),
}


# Release that removes the deprecated private-only entities.
PRIVATE_ONLY_BREAKS_IN = "2027.1.0"

# Device setup and device data entities that rely on the private API, keyed by
# device model and then by (platform, key). Scoped by model because other
# devices may reuse the keys.
PRIVATE_ONLY_ENTITIES: dict[ModelType, frozenset[tuple[Platform, str]]] = {
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
def async_deprecate_camera_setting_mirrors(
    hass: HomeAssistant, entry: UFPConfigEntry, bootstrap: Bootstrap
) -> None:
    """Deprecate the read-only mirrors of the public camera controls.

    These controls write through the public API, so every user gets them and
    the ``PermRequired.NO_WRITE`` mirrors only duplicate them.

    Runs after platform setup so the repair can name the replacement.

    Added in 2026.11.0
    """
    _async_deprecate_setting_mirrors(
        hass,
        entry,
        {camera.mac for camera in bootstrap.cameras.values()},
        _CAMERA_MIRROR_REPLACEMENTS,
        CAMERA_SETTING_MIRROR_BREAKS_IN,
    )


@callback
def async_is_new_private_only_entity(
    hass: HomeAssistant, model: ModelType | None, mac: str, key: str
) -> bool:
    """Return whether a deprecated private-only entity is not registered yet.

    New installs do not get entities that are about to be removed.
    """
    if model is None or model not in PRIVATE_ONLY_ENTITIES:
        return False
    platforms = [
        platform
        for platform, entity_key in PRIVATE_ONLY_ENTITIES[model]
        if entity_key == key
    ]
    if not platforms:
        return False
    registry = er.async_get(hass)
    return not any(
        registry.async_get_entity_id(platform, DOMAIN, f"{mac}_{key}")
        for platform in platforms
    )


@callback
def async_deprecate_private_only_entities(
    hass: HomeAssistant, entry: UFPConfigEntry, bootstrap: Bootstrap
) -> None:
    """Deprecate the entities that only the private API provides.

    The official API does not provide them, and they are not requested from
    Ubiquiti.

    Waits for startup to finish: before the automations are loaded, every entity
    looks unused and the repair would be dropped.

    Added in 2026.11.0
    """

    @callback
    def _async_deprecate(_hass: HomeAssistant) -> None:
        models: dict[str, ModelType] = {bootstrap.nvr.mac: ModelType.NVR}
        for devices, device_model in (
            (bootstrap.cameras, ModelType.CAMERA),
            (bootstrap.lights, ModelType.LIGHT),
            (bootstrap.viewers, ModelType.VIEWPORT),
            (bootstrap.sensors, ModelType.SENSOR),
            (bootstrap.chimes, ModelType.CHIME),
        ):
            models.update(
                dict.fromkeys((d.mac for d in devices.values()), device_model)
            )
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            mac, _, key = entity.unique_id.partition("_")
            model = models.get(mac)
            if (
                model is None
                or (entity.domain, key) not in PRIVATE_ONLY_ENTITIES[model]
            ):
                continue
            _async_repair_if_used(
                hass,
                entity,
                # SSH, mount type and paired camera share a unique_id across
                # two platforms.
                f"private_only_entity_deprecated_{entity.domain}_{entity.unique_id}",
                "private_only_entity_deprecated",
                breaks_in=PRIVATE_ONLY_BREAKS_IN,
            )

    entry.async_on_unload(async_at_started(hass, _async_deprecate))


@callback
def _async_deprecate_setting_mirrors(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    macs: set[str],
    replacements: _MirrorReplacements,
    breaks_in: str,
) -> None:
    """Raise a repair for each used mirror, pointing at its replacement.

    The mirror keys are shared across device types, so the match is scoped to
    ``macs``. Waits for startup to finish, like ``_async_remove_when_started``.
    """
    if not macs:
        return

    @callback
    def _async_deprecate(_hass: HomeAssistant) -> None:
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            mac, _, key = entity.unique_id.partition("_")
            mirror = (entity.domain, key)
            if mirror not in replacements or mac not in macs:
                continue
            platform, replacement_key, translation_key = replacements[mirror]
            replacement_id = registry.async_get_entity_id(
                platform,
                DOMAIN,
                mac if replacement_key is None else f"{mac}_{replacement_key}",
            )
            # Nothing to point the repair at before the replacement exists.
            if replacement_id is None:
                continue
            _async_repair_if_used(
                hass,
                entity,
                f"setting_mirror_deprecated_{entity.unique_id}",
                translation_key,
                {"replacement": replacement_id},
                breaks_in=breaks_in,
            )

    entry.async_on_unload(async_at_started(hass, _async_deprecate))


# Camera entities on the private API that a public event entity replaces, keyed
# by their own (platform, key), pointing at the event entity and the repair text.
_RING_AND_MOTION_SENSOR_REPLACEMENTS: dict[
    tuple[str, str], tuple[Platform, str | None, str]
] = {
    (Platform.BINARY_SENSOR, "doorbell"): (
        Platform.EVENT,
        "doorbell",
        "doorbell_sensor_deprecated",
    ),
    (Platform.SENSOR, "doorbell_last_trip_time"): (
        Platform.EVENT,
        "doorbell",
        "last_event_sensor_deprecated",
    ),
    (Platform.SENSOR, "motion_last_trip_time"): (
        Platform.EVENT,
        "motion_detection",
        "last_event_sensor_deprecated",
    ),
}


@callback
def async_is_new_ring_or_motion_sensor(
    hass: HomeAssistant, platform: Platform, mac: str, key: str
) -> bool:
    """Return whether a deprecated camera ring or motion sensor is not registered yet.

    New installs do not get entities that are about to be removed. Matched per
    platform: the doorbell text and event entities share the binary sensor's key.
    """
    if (platform, key) not in _RING_AND_MOTION_SENSOR_REPLACEMENTS:
        return False
    return (
        er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{mac}_{key}") is None
    )


@callback
def async_deprecate_ring_and_motion_sensors(
    hass: HomeAssistant, entry: UFPConfigEntry, bootstrap: Bootstrap
) -> None:
    """Deprecate the camera ring and motion sensors on the private API.

    The doorbell and motion detection event entities cover them through the
    public API.

    Runs after platform setup so the repair can name the replacement.

    Added in 2026.11.0
    """
    _async_deprecate_setting_mirrors(
        hass,
        entry,
        {camera.mac for camera in bootstrap.cameras.values()},
        _RING_AND_MOTION_SENSOR_REPLACEMENTS,
        PRIVATE_ONLY_BREAKS_IN,
    )
