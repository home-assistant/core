"""Test the UniFi Protect setup flow."""

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from uiprotect.data import Camera, Sensor
from uiprotect.data.public_devices import SensorFeatureCapability

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.migrate import (
    async_migrate_sensor_signal_strength,
    async_remove_hdr_switch,
    async_remove_sense_setting_mirrors,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .utils import MockUFPFixture, init_entry, make_public_sensor, setup_public_sensor


async def _load_automation(hass: HomeAssistant, entity_id: str):
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "test1",
                    "trigger": [
                        {"platform": "state", "entity_id": entity_id},
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": entity_id},
                        },
                    ],
                    "condition": {
                        "condition": "state",
                        "entity_id": entity_id,
                        "state": "on",
                    },
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": entity_id},
                        },
                    ],
                },
            ]
        },
    )


async def test_migrate_remove_aiport_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
) -> None:
    """A leftover AI Port device/entity is removed by type, bootstrap-independent."""
    mac = "AABBCCDDEEFF"
    device = device_registry.async_get_or_create(
        config_entry_id=ufp.entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        model_id="AI Port",
    )
    entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{mac}_uptime",
        config_entry=ufp.entry,
        device_id=device.id,
    )

    # AI Port deliberately absent from the bootstrap — cleanup is registry-based
    await init_entry(hass, ufp, [])

    assert entity_registry.async_get(entity.entity_id) is None
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), ufp.entry.entry_id
        )
        is None
    )


async def test_migrate_insecure_camera_redirected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A legacy insecure camera entity is redirected to the secure stream."""
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    # the insecure entity now carries the secure unique_id (history preserved)
    migrated = entity_registry.async_get(insecure.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{doorbell.mac}_0"
    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0_insecure"
        )
        is None
    )


async def test_migrate_insecure_camera_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A redundant, unused insecure entity is removed silently."""
    entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0"
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
        )
        is None
    )


async def test_migrate_insecure_camera_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Removing an insecure entity that is still used raises an actionable repair."""
    secure = entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, insecure.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == insecure.entity_id
    assert issue.translation_placeholders["replacement"] == secure.entity_id


async def test_migrate_insecure_camera_removed_disabled_not_repaired(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A disabled insecure entity is removed without a repair even if referenced."""
    entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await _load_automation(hass, insecure.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
        )
        is None
    )


SENSE_SETTING_MIRRORS = [
    pytest.param(Platform.BINARY_SENSOR, "motion_enabled", id="motion_enabled"),
    pytest.param(Platform.BINARY_SENSOR, "temperature", id="temperature"),
    pytest.param(Platform.BINARY_SENSOR, "humidity", id="humidity"),
    pytest.param(Platform.BINARY_SENSOR, "light", id="light"),
    pytest.param(Platform.BINARY_SENSOR, "alarm", id="alarm"),
    pytest.param(Platform.SENSOR, "sensitivity", id="sensitivity"),
]


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.unifiprotect.issues.sense_setting_mirror_deprecated.title",
            "component.unifiprotect.issues.sense_setting_mirror_deprecated.description",
        ]
    ],
)
@pytest.mark.parametrize(("platform", "key"), SENSE_SETTING_MIRRORS)
async def test_migrate_sense_setting_mirror_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    platform: Platform,
    key: str,
) -> None:
    """An unused setting mirror is removed with its stored deprecation repair."""
    setup_public_sensor(ufp)
    mirror = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{sensor_all.mac}_{key}", config_entry=ufp.entry
    )
    deprecation_issue = f"sense_setting_mirror_deprecated_{mirror.unique_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        deprecation_issue,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="sense_setting_mirror_deprecated",
    )

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is None
    assert issue_registry.async_get_issue(DOMAIN, deprecation_issue) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"sense_setting_mirror_removed_{mirror.unique_id}"
        )
        is None
    )


@pytest.mark.parametrize(
    ("capabilities", "translation_key", "has_replacement"),
    [
        pytest.param(None, "sense_setting_mirror_removed", True, id="replacement"),
        pytest.param(
            set(),
            "sense_setting_mirror_removed_no_replacement",
            False,
            id="no_replacement",
        ),
    ],
)
async def test_migrate_sense_setting_mirror_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    capabilities: set[SensorFeatureCapability] | None,
    translation_key: str,
    has_replacement: bool,
) -> None:
    """Removing a used mirror raises a repair naming the switch set up beside it."""
    setup_public_sensor(ufp, capabilities=capabilities)
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"sense_setting_mirror_removed_{mirror.unique_id}"
    )
    assert issue is not None
    assert issue.is_persistent
    assert issue.translation_key == translation_key
    assert issue.translation_placeholders["entity_id"] == mirror.entity_id
    replacement = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{sensor_all.mac}_alarm"
    )
    assert (replacement is not None) is has_replacement
    assert issue.translation_placeholders.get("replacement") == replacement


@pytest.mark.parametrize(
    ("platform", "key"),
    [
        pytest.param(Platform.BINARY_SENSOR, "motion_enabled", id="motion_enabled"),
        pytest.param(Platform.BINARY_SENSOR, "light", id="light"),
        pytest.param(Platform.SENSOR, "sensitivity", id="sensitivity"),
    ],
)
async def test_migrate_sense_setting_mirror_keeps_other_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    sensor_all: Sensor,
    platform: Platform,
    key: str,
) -> None:
    """Camera and light entities share the mirror keys and stay."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )

    async_remove_sense_setting_mirrors(hass, ufp.entry, {sensor_all.mac})

    assert entity_registry.async_get(entity.entity_id) is not None


async def test_migrate_sense_setting_mirror_removed_public_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_all: Sensor,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A mirror left by full access is also removed in API key only mode."""
    ufp_public_only.api.public_bootstrap.sensors[sensor_all.id] = make_public_sensor(
        sensor_all
    )
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp_public_only.entry,
    )

    await setup_public_only()

    assert entity_registry.async_get(mirror.entity_id) is None


REMOVED_ENTITIES = [
    pytest.param(
        Platform.BINARY_SENSOR,
        "smart_obj_package",
        "package_binary_sensor_removed",
        id="package_binary_sensor",
    ),
    pytest.param(Platform.SWITCH, "hdr_mode", "hdr_switch_removed", id="hdr_switch"),
]


@pytest.mark.parametrize(("platform", "key", "issue"), REMOVED_ENTITIES)
async def test_migrate_removed_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    issue: str,
) -> None:
    """An unused removed entity is removed silently."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(entity.entity_id) is None
    assert (
        issue_registry.async_get_issue(DOMAIN, f"{issue}_{doorbell.mac}_{key}") is None
    )


@pytest.mark.parametrize(("platform", "key", "issue"), REMOVED_ENTITIES)
async def test_migrate_removed_entity_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    issue: str,
) -> None:
    """Removing a used entity raises an actionable repair."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(entity.entity_id) is None
    repair = issue_registry.async_get_issue(DOMAIN, f"{issue}_{doorbell.mac}_{key}")
    assert repair is not None
    assert repair.translation_key == issue
    assert repair.is_persistent
    assert repair.translation_placeholders["entity_id"] == entity.entity_id


@pytest.mark.parametrize(("platform", "key", "issue"), REMOVED_ENTITIES)
async def test_migrate_removed_entity_disabled_not_repaired(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    issue: str,
) -> None:
    """A disabled removed entity is removed without a repair even if referenced."""
    entity = entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        f"{doorbell.mac}_{key}",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(entity.entity_id) is None
    assert (
        issue_registry.async_get_issue(DOMAIN, f"{issue}_{doorbell.mac}_{key}") is None
    )


@pytest.mark.parametrize("platform", [Platform.BINARY_SENSOR, Platform.SELECT])
async def test_migrate_hdr_switch_keeps_other_platforms(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
) -> None:
    """Only the switch goes; the HDR binary sensor and select share its key."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_hdr_mode", config_entry=ufp.entry
    )

    # Run the migration alone: setup would recreate the entity.
    async_remove_hdr_switch(hass, ufp.entry)

    assert entity_registry.async_get(entity.entity_id) is not None


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.unifiprotect.issues.deprecate_hdr_switch.title",
            "component.unifiprotect.issues.deprecate_hdr_switch.description",
        ]
    ],
)
async def test_migrate_hdr_switch_clears_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """The stored deprecation repair is deleted with the switch."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecate_hdr_switch",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecate_hdr_switch",
    )

    async_remove_hdr_switch(hass, ufp.entry)

    assert issue_registry.async_get_issue(DOMAIN, "deprecate_hdr_switch") is None


async def test_migrate_sensor_signal_strength_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """The ``ble_signal`` unique_id moves to ``signal_strength``, keeping the entity."""
    entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_ble_signal",
        config_entry=ufp.entry,
        suggested_object_id="old_signal",
    )

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    migrated = entity_registry.async_get(entity.entity_id)
    assert migrated is not None
    assert migrated.id == entity.id
    assert migrated.entity_id == "sensor.old_signal"
    assert migrated.unique_id == f"{sensor_all.mac}_signal_strength"


async def test_migrate_sensor_signal_strength_drops_duplicate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """An old ``ble_signal`` entry is dropped when the new one already exists."""
    old = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, f"{sensor_all.mac}_ble_signal", config_entry=ufp.entry
    )
    new = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_signal_strength",
        config_entry=ufp.entry,
    )

    async_migrate_sensor_signal_strength(hass, ufp.entry)

    assert entity_registry.async_get(old.entity_id) is None
    assert entity_registry.async_get(new.entity_id) is not None
