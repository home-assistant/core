"""Test the UniFi Protect setup flow."""

from collections.abc import Callable, Coroutine
import dataclasses
import logging
from typing import Any
from unittest.mock import Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from uiprotect.data import (
    Camera,
    Light,
    ModelType,
    Sensor,
    SmartDetectAudioType,
    SmartDetectObjectType,
)
from uiprotect.data.public_devices import SensorFeatureCapability

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.migrate import (
    async_migrate_sensor_signal_strength,
    async_remove_hdr_switch,
    async_remove_private_api_entities,
    async_remove_sense_setting_mirrors,
)
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .utils import (
    MockUFPFixture,
    init_entry,
    make_public_light,
    make_public_sensor,
    setup_public_camera,
    setup_public_light,
    setup_public_sensor,
)


async def _load_automation(hass: HomeAssistant, *entity_ids: str):
    """Load one automation per entity id; the component sets up only once."""
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": f"test{index}",
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
                }
                for index, entity_id in enumerate(entity_ids, 1)
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
    assert issue.config_entry_id == ufp.entry.entry_id
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
    assert issue.config_entry_id == ufp.entry.entry_id
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
    issue_registry: ir.IssueRegistry,
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
    await _load_automation(hass, mirror.entity_id)

    await setup_public_only()

    assert entity_registry.async_get(mirror.entity_id) is None
    # Runs after platform setup, so the repair names the alarm switch.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"sense_setting_mirror_removed_{mirror.unique_id}"
    )
    assert issue is not None
    assert issue.translation_key == "sense_setting_mirror_removed"


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
    assert repair.config_entry_id == ufp.entry.entry_id
    assert repair.translation_key == issue
    assert repair.is_persistent
    assert repair.translation_placeholders["entity_id"] == entity.entity_id


@pytest.mark.parametrize(("platform", "key", "issue"), REMOVED_ENTITIES)
async def test_migrate_removed_entity_repair_removed_with_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    issue: str,
) -> None:
    """The persistent removal repair goes away with its config entry."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)
    issue_id = f"{issue}_{doorbell.mac}_{key}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("platform", "unique_id_suffix", "issue", "translation_key", "placeholders"),
    [
        pytest.param(
            Platform.CAMERA,
            "0_insecure",
            "insecure_camera_removed",
            "insecure_camera_removed",
            {"replacement": "camera.secure"},
            id="insecure_camera",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            "smart_obj_package",
            "package_binary_sensor_removed",
            "package_binary_sensor_removed",
            {},
            id="package_binary_sensor",
        ),
        pytest.param(
            Platform.SWITCH,
            "hdr_mode",
            "hdr_switch_removed",
            "hdr_switch_removed",
            {},
            id="hdr_switch",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            "alarm",
            "sense_setting_mirror_removed",
            "sense_setting_mirror_removed",
            {"replacement": "switch.alarm"},
            id="sense_setting_mirror",
        ),
        pytest.param(
            Platform.SENSOR,
            "sensitivity",
            "sense_setting_mirror_removed",
            "sense_setting_mirror_removed_no_replacement",
            {},
            id="sense_setting_mirror_no_replacement",
        ),
    ],
)
async def test_link_unlinked_removal_repair(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    unique_id_suffix: str,
    issue: str,
    translation_key: str,
    placeholders: dict[str, str],
) -> None:
    """A removal repair raised before it was linked is linked to its entry."""
    unique_id = f"{doorbell.mac}_{unique_id_suffix}"
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    entity_registry.async_remove(entity.entity_id)
    issue_id = f"{issue}_{unique_id}"
    # The repair as earlier releases raised it, ignored by the user.
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `automation.test`\n",
            **placeholders,
        },
    )
    ir.async_ignore_issue(hass, DOMAIN, issue_id, True)
    ignored = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert ignored is not None

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    linked = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert linked == dataclasses.replace(ignored, config_entry_id=ufp.entry.entry_id)
    assert linked.dismissed_version is not None

    await hass.config_entries.async_remove(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    (
        "deleted_platform",
        "deleted_unique_id",
        "deleted_owner",
        "issue_owner",
        "persistent",
    ),
    [
        pytest.param(
            Platform.SWITCH,
            "112233445566_hdr_mode",
            "this",
            None,
            True,
            id="unknown_mac",
        ),
        pytest.param(
            Platform.SWITCH, "{mac}_hdr_mode", "other", None, True, id="other_nvr"
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            "{mac}_hdr_mode",
            "this",
            None,
            True,
            id="other_platform",
        ),
        pytest.param(
            Platform.SWITCH, "{mac}_hdr_mode", "this", "other", True, id="linked"
        ),
        pytest.param(
            Platform.SWITCH,
            "{mac}_hdr_mode",
            "this",
            None,
            False,
            id="not_persistent",
        ),
    ],
)
async def test_link_removal_repair_not_owned(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    deleted_platform: Platform,
    deleted_unique_id: str,
    deleted_owner: str,
    issue_owner: str | None,
    persistent: bool,
) -> None:
    """A removal repair this entry does not own the entity of is left alone."""
    # Another NVR; disabled so it is not set up with this one.
    other_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="other", disabled_by=ConfigEntryDisabler.USER
    )
    other_entry.add_to_hass(hass)
    entries = {"this": ufp.entry, "other": other_entry}
    entity = entity_registry.async_get_or_create(
        deleted_platform,
        DOMAIN,
        deleted_unique_id.format(mac=doorbell.mac),
        config_entry=entries[deleted_owner],
    )
    entity_registry.async_remove(entity.entity_id)
    issue_id = f"hdr_switch_removed_{doorbell.mac}_hdr_mode"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        config_entry_id={"other": other_entry.entry_id, None: None}[issue_owner],
        is_fixable=False,
        is_persistent=persistent,
        severity=ir.IssueSeverity.WARNING,
        translation_key="hdr_switch_removed",
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `automation.test`\n",
        },
    )
    before = issue_registry.async_get_issue(DOMAIN, issue_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) == before


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


@pytest.mark.parametrize(
    ("platform", "key", "issue"),
    [
        *REMOVED_ENTITIES,
        pytest.param(
            Platform.CAMERA,
            "0_insecure",
            "insecure_camera_removed",
            id="insecure_camera",
        ),
    ],
)
async def test_migrate_removed_entity_waits_for_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    issue: str,
) -> None:
    """A used entity is only removed, with its repair, once startup is done."""
    # The insecure camera is only removed next to its secure counterpart. The
    # other entities ignore it.
    entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )
    hass.set_state(CoreState.starting)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)
    await _load_automation(hass, entity.entity_id)
    assert entity_registry.async_get(entity.entity_id) is not None
    assert not issue_registry.issues

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity.entity_id) is None
    assert issue_registry.async_get_issue(DOMAIN, f"{issue}_{doorbell.mac}_{key}")


@pytest.mark.parametrize(
    ("platform", "device", "key"),
    [
        pytest.param(Platform.SWITCH, "doorbell", "hdr_mode", id="removal"),
        pytest.param(Platform.BINARY_SENSOR, "light", "light", id="private_api"),
    ],
)
async def test_migrate_unload_before_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    light: Light,
    request: pytest.FixtureRequest,
    platform: Platform,
    device: str,
    key: str,
) -> None:
    """An entry unloaded before startup finishes leaves its entities alone."""
    setup_public_light(ufp)
    mac = request.getfixturevalue(device).mac
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)
    hass.set_state(CoreState.starting)
    await init_entry(hass, ufp, [doorbell, light], regenerate_ids=False)

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity.entity_id) is not None
    assert not issue_registry.issues


async def test_migrate_removed_entity_deleted_before_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An entity the user deletes during startup is skipped."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{doorbell.mac}_hdr_mode", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)
    hass.set_state(CoreState.starting)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    entity_registry.async_remove(entity.entity_id)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not issue_registry.issues
    # A failing STARTED listener is only logged, not raised.
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_migrate_removed_entity_renamed_before_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """An entity renamed during startup is still removed with its repair."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{doorbell.mac}_hdr_mode", config_entry=ufp.entry
    )
    hass.set_state(CoreState.starting)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    renamed = entity_registry.async_update_entity(
        entity.entity_id, new_entity_id="switch.renamed_hdr"
    )
    await _load_automation(hass, renamed.entity_id)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert entity_registry.async_get(renamed.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"hdr_switch_removed_{doorbell.mac}_hdr_mode"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == renamed.entity_id


async def test_migrate_sense_setting_mirror_waits_for_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A used sense mirror is only removed, with its repair, once startup is done."""
    setup_public_sensor(ufp)
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp.entry,
    )
    hass.set_state(CoreState.starting)

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)
    await _load_automation(hass, mirror.entity_id)
    assert entity_registry.async_get(mirror.entity_id) is not None

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert entity_registry.async_get(mirror.entity_id) is None
    assert issue_registry.async_get_issue(
        DOMAIN, f"sense_setting_mirror_removed_{mirror.unique_id}"
    )


_CAMERA_SWITCH_MIRRORS = (
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


@pytest.mark.parametrize(
    (
        "device",
        "platform",
        "key",
        "replacement_platform",
        "replacement_suffix",
        "translation_key",
    ),
    [
        pytest.param(
            "light",
            Platform.BINARY_SENSOR,
            "light",
            Platform.LIGHT,
            "",
            "setting_mirror_removed",
            id="light_light",
        ),
        pytest.param(
            "light",
            Platform.BINARY_SENSOR,
            "status_light",
            Platform.SWITCH,
            "_status_light",
            "setting_mirror_removed",
            id="light_status_light",
        ),
        pytest.param(
            "light",
            Platform.SENSOR,
            "sensitivity",
            Platform.NUMBER,
            "_sensitivity",
            "setting_mirror_removed",
            id="light_sensitivity",
        ),
        pytest.param(
            "light",
            Platform.SENSOR,
            "light_motion",
            Platform.SELECT,
            "_light_motion",
            "setting_mirror_removed_light_mode",
            id="light_light_motion",
        ),
        *(
            pytest.param(
                "doorbell",
                Platform.BINARY_SENSOR,
                key,
                Platform.SWITCH,
                f"_{key}",
                "setting_mirror_removed",
                id=f"camera_{key}",
            )
            for key in _CAMERA_SWITCH_MIRRORS
        ),
        pytest.param(
            "doorbell",
            Platform.BINARY_SENSOR,
            "hdr_mode",
            Platform.SELECT,
            "_hdr_mode",
            "setting_mirror_removed_hdr_mode",
            id="camera_hdr_mode",
        ),
        pytest.param(
            "doorbell",
            Platform.SENSOR,
            "mic_level",
            Platform.NUMBER,
            "_mic_level",
            "setting_mirror_removed_mic_level",
            id="camera_mic_level",
        ),
        pytest.param(
            "doorbell",
            Platform.SENSOR,
            "doorbell_text",
            Platform.TEXT,
            "_doorbell",
            "setting_mirror_removed_doorbell_text",
            id="camera_doorbell_text",
        ),
        pytest.param(
            "doorbell",
            Platform.BINARY_SENSOR,
            "doorbell",
            Platform.EVENT,
            "_doorbell",
            "doorbell_sensor_removed",
            id="camera_doorbell_binary_sensor",
        ),
        pytest.param(
            "doorbell",
            Platform.SENSOR,
            "doorbell_last_trip_time",
            Platform.EVENT,
            "_doorbell",
            "last_event_sensor_removed",
            id="camera_last_ring_sensor",
        ),
        pytest.param(
            "doorbell",
            Platform.SENSOR,
            "motion_last_trip_time",
            Platform.EVENT,
            "_motion_detection",
            "last_event_sensor_removed",
            id="camera_last_motion_sensor",
        ),
    ],
)
async def test_migrate_replaced_entity_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    light: Light,
    request: pytest.FixtureRequest,
    device: str,
    platform: Platform,
    key: str,
    replacement_platform: Platform,
    replacement_suffix: str,
    translation_key: str,
) -> None:
    """Removing a used replaced entity raises a repair naming its replacement."""
    # Every detection type, so each detection switch exists as a replacement.
    doorbell.feature_flags.smart_detect_types = [
        t for t in SmartDetectObjectType if t.audio_type is None
    ]
    doorbell.feature_flags.smart_detect_audio_types = list(SmartDetectAudioType)
    setup_public_camera(ufp)
    setup_public_light(ufp)
    mac = request.getfixturevalue(device).mac
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell, light], regenerate_ids=False)

    assert entity_registry.async_get(entity.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_{platform}_{mac}_{key}"
    )
    assert issue is not None
    assert issue.config_entry_id == ufp.entry.entry_id
    assert issue.is_persistent
    assert issue.translation_key == translation_key
    assert issue.translation_placeholders["entity_id"] == entity.entity_id
    replacement_id = entity_registry.async_get_entity_id(
        replacement_platform, DOMAIN, f"{mac}{replacement_suffix}"
    )
    assert replacement_id is not None
    assert issue.translation_placeholders["replacement"] == replacement_id


CAMERA_MAC = "AABBCCDDEE01"
LIGHT_MAC = "AABBCCDDEE02"
VIEWER_MAC = "AABBCCDDEE03"
SENSOR_MAC = "AABBCCDDEE04"
NVR_MAC = "AABBCCDDEE05"
CHIME_MAC = "AABBCCDDEE06"


def _devices() -> dict[ModelType, list[Mock]]:
    """Return one device of each model."""
    return {
        ModelType.CAMERA: [Mock(mac=CAMERA_MAC)],
        ModelType.LIGHT: [Mock(mac=LIGHT_MAC)],
        ModelType.VIEWPORT: [Mock(mac=VIEWER_MAC)],
        ModelType.SENSOR: [Mock(mac=SENSOR_MAC)],
        ModelType.CHIME: [Mock(mac=CHIME_MAC)],
    }


async def test_migrate_replaced_entity_removed_without_replacement(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Without its replacement, a used entity gets the generic removal repair."""
    entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{LIGHT_MAC}_light", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(entity.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_binary_sensor_{LIGHT_MAC}_light"
    )
    assert issue is not None
    assert issue.translation_key == "private_api_entity_removed"
    assert "replacement" not in issue.translation_placeholders


@pytest.mark.parametrize(
    ("mac", "platform", "key"),
    [
        pytest.param(CAMERA_MAC, Platform.SWITCH, "ssh", id="camera_ssh_switch"),
        pytest.param(
            CAMERA_MAC, Platform.BINARY_SENSOR, "ssh", id="camera_ssh_binary_sensor"
        ),
        pytest.param(CAMERA_MAC, Platform.SENSOR, "lens_type", id="camera_lens_type"),
        pytest.param(CAMERA_MAC, Platform.SENSOR, "voltage", id="camera_voltage"),
        pytest.param(LIGHT_MAC, Platform.SWITCH, "ssh", id="light_ssh_switch"),
        pytest.param(
            LIGHT_MAC, Platform.BINARY_SENSOR, "ssh", id="light_ssh_binary_sensor"
        ),
        pytest.param(
            LIGHT_MAC, Platform.SELECT, "paired_camera", id="light_paired_camera_select"
        ),
        pytest.param(
            LIGHT_MAC, Platform.SENSOR, "paired_camera", id="light_paired_camera_sensor"
        ),
        pytest.param(VIEWER_MAC, Platform.SWITCH, "ssh", id="viewer_ssh_switch"),
        pytest.param(
            VIEWER_MAC, Platform.BINARY_SENSOR, "ssh", id="viewer_ssh_binary_sensor"
        ),
        pytest.param(
            SENSOR_MAC, Platform.SELECT, "mount_type", id="sensor_mount_type_select"
        ),
        pytest.param(
            SENSOR_MAC, Platform.SENSOR, "mount_type", id="sensor_mount_type_sensor"
        ),
        pytest.param(
            SENSOR_MAC,
            Platform.SELECT,
            "paired_camera",
            id="sensor_paired_camera_select",
        ),
        pytest.param(
            SENSOR_MAC,
            Platform.SENSOR,
            "paired_camera",
            id="sensor_paired_camera_sensor",
        ),
        pytest.param(NVR_MAC, Platform.SWITCH, "analytics_enabled", id="nvr_analytics"),
        pytest.param(NVR_MAC, Platform.SWITCH, "insights_enabled", id="nvr_insights"),
        *(
            pytest.param(CAMERA_MAC, Platform.SENSOR, key, id=f"camera_{key}")
            for key in (
                "uptime",
                "phy_rate",
                "oldest_recording",
                "storage_used",
                "write_rate",
                "stats_rx",
                "stats_tx",
            )
        ),
        *(
            pytest.param(mac, Platform.SENSOR, key, id=f"{name}_{key}")
            for mac, name in (
                (LIGHT_MAC, "light"),
                (VIEWER_MAC, "viewer"),
                (SENSOR_MAC, "sensor"),
                (CHIME_MAC, "chime"),
            )
            for key in ("uptime", "phy_rate")
        ),
        *(
            pytest.param(NVR_MAC, Platform.SENSOR, key, id=f"nvr_{key}")
            for key in (
                "uptime",
                "cpu_utilization",
                "cpu_temperature",
                "memory_utilization",
            )
        ),
    ],
)
async def test_migrate_private_only_entity_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    mac: str,
    platform: Platform,
    key: str,
) -> None:
    """Removing a used private-only entity raises a repair."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(entity.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_{platform}_{mac}_{key}"
    )
    assert issue is not None
    assert issue.config_entry_id == ufp.entry.entry_id
    assert issue.is_persistent
    assert issue.translation_key == "private_api_entity_removed"
    assert issue.translation_placeholders["entity_id"] == entity.entity_id


@pytest.mark.parametrize(
    ("platform", "unique_id"),
    [
        pytest.param(Platform.SENSOR, f"{CAMERA_MAC}_ssh", id="key_on_other_platform"),
        pytest.param(
            Platform.SELECT, f"{CAMERA_MAC}_mount_type", id="key_of_other_model"
        ),
        pytest.param(
            Platform.BINARY_SENSOR, f"{LIGHT_MAC}_high_fps", id="camera_key_on_light"
        ),
        pytest.param(
            Platform.SENSOR, f"{CAMERA_MAC}_sensitivity", id="light_key_on_camera"
        ),
        pytest.param(
            Platform.SENSOR,
            f"{SENSOR_MAC}_motion_last_trip_time",
            id="camera_key_on_sensor",
        ),
        pytest.param(
            Platform.SENSOR, f"{CAMERA_MAC}_x_voltage", id="key_inside_unique_id"
        ),
        pytest.param(Platform.SENSOR, "AABBCCDDEE99_voltage", id="unknown_device"),
        pytest.param(Platform.TEXT, f"{CAMERA_MAC}_doorbell", id="shared_key"),
    ],
)
async def test_migrate_private_api_entity_not_matched(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    platform: Platform,
    unique_id: str,
) -> None:
    """Only a removed key on its platform and device model counts."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(entity.entity_id) is not None
    assert not issue_registry.issues


async def test_migrate_private_api_entity_shared_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Both entities sharing a unique_id go; only the used one gets a repair."""
    used = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    unused = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    await _load_automation(hass, used.entity_id)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(used.entity_id) is None
    assert entity_registry.async_get(unused.entity_id) is None
    assert issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_binary_sensor_{CAMERA_MAC}_ssh"
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"private_api_entity_removed_switch_{CAMERA_MAC}_ssh"
        )
        is None
    )


async def test_migrate_private_api_entity_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """A disabled entity is removed without a repair even if referenced."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{CAMERA_MAC}_ssh",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    await _load_automation(hass, entity.entity_id)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(entity.entity_id) is None
    assert not issue_registry.issues


@pytest.mark.parametrize(
    ("platform", "unique_id", "deprecation_issue"),
    [
        pytest.param(
            Platform.SWITCH,
            f"{CAMERA_MAC}_ssh",
            f"private_only_entity_deprecated_switch_{CAMERA_MAC}_ssh",
            id="private_only",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            f"{LIGHT_MAC}_light",
            f"setting_mirror_deprecated_{LIGHT_MAC}_light",
            id="setting_mirror",
        ),
    ],
)
async def test_migrate_private_api_entity_clears_deprecation_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    platform: Platform,
    unique_id: str,
    deprecation_issue: str,
) -> None:
    """An unused entity is removed silently with its deprecation repair."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        deprecation_issue,
        is_fixable=False,
        breaks_in_ha_version="2027.1.0",
        severity=ir.IssueSeverity.WARNING,
        translation_key="private_api_entity_removed",
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `automation.gone`\n",
        },
    )

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())

    assert entity_registry.async_get(entity.entity_id) is None
    assert not issue_registry.issues


async def test_migrate_private_api_entity_waits_for_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """A used entity is only removed, with its repair, once startup is done."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    hass.set_state(CoreState.starting)

    async_remove_private_api_entities(hass, ufp.entry, NVR_MAC, _devices())
    await _load_automation(hass, entity.entity_id)
    assert entity_registry.async_get(entity.entity_id) is not None
    assert not issue_registry.issues

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity.entity_id) is None
    assert issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_switch_{CAMERA_MAC}_ssh"
    )


async def test_migrate_private_api_entities_on_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Setup removes a used private-only entity and raises the repair."""
    nvr_mac = ufp.api.bootstrap.nvr.mac
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{nvr_mac}_analytics_enabled",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [])

    assert entity_registry.async_get(entity.entity_id) is None
    assert issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_switch_{nvr_mac}_analytics_enabled"
    )


async def test_migrate_private_api_entity_removed_public_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """An entity left by full access is also removed in API key only mode."""
    ufp_public_only.api.public_bootstrap.lights[light.id] = make_public_light(light)
    entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{light.mac}_status_light",
        config_entry=ufp_public_only.entry,
    )
    await _load_automation(hass, entity.entity_id)

    await setup_public_only()

    assert entity_registry.async_get(entity.entity_id) is None
    # Runs after platform setup, so the repair names the status light switch.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"private_api_entity_removed_binary_sensor_{light.mac}_status_light"
    )
    assert issue is not None
    assert issue.translation_key == "setting_mirror_removed"
