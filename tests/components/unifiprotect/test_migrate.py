"""Test the UniFi Protect setup flow."""

from collections.abc import Callable, Coroutine
import logging
from typing import Any
from unittest.mock import Mock

import pytest
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
    CAMERA_SETTING_MIRROR_BREAKS_IN,
    LIGHT_SETTING_MIRROR_BREAKS_IN,
    PRIVATE_ONLY_BREAKS_IN,
    async_deprecate_light_setting_mirrors,
    async_deprecate_private_only_entities,
    async_is_new_private_only_entity,
    async_is_new_ring_or_motion_sensor,
    async_migrate_sensor_signal_strength,
    async_remove_hdr_switch,
    async_remove_sense_setting_mirrors,
)
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


@pytest.mark.parametrize(
    (
        "platform",
        "key",
        "replacement_platform",
        "replacement_suffix",
        "translation_key",
    ),
    [
        (
            Platform.BINARY_SENSOR,
            "light",
            Platform.LIGHT,
            "",
            "setting_mirror_deprecated",
        ),
        (
            Platform.BINARY_SENSOR,
            "status_light",
            Platform.SWITCH,
            "_status_light",
            "setting_mirror_deprecated",
        ),
        (
            Platform.SENSOR,
            "sensitivity",
            Platform.NUMBER,
            "_sensitivity",
            "setting_mirror_deprecated",
        ),
        (
            Platform.SENSOR,
            "light_motion",
            Platform.SELECT,
            "_light_motion",
            "setting_mirror_deprecated_light_mode",
        ),
    ],
)
async def test_migrate_light_setting_mirror_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    light: Light,
    platform: Platform,
    key: str,
    replacement_platform: Platform,
    replacement_suffix: str,
    translation_key: str,
) -> None:
    """A used light mirror gets a repair naming the control that replaces it."""
    setup_public_light(ufp)
    mirror = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{light.mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"setting_mirror_deprecated_{light.mac}_{key}"
    )
    assert issue is not None
    assert issue.translation_key == translation_key
    assert issue.breaks_in_ha_version == LIGHT_SETTING_MIRROR_BREAKS_IN
    assert issue.translation_placeholders["entity_id"] == mirror.entity_id
    replacement_id = entity_registry.async_get_entity_id(
        replacement_platform, DOMAIN, f"{light.mac}{replacement_suffix}"
    )
    assert replacement_id is not None
    assert issue.translation_placeholders["replacement"] == replacement_id


async def test_migrate_light_setting_mirror_repair_clears_when_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """The deprecation repair goes away once the last usage is gone."""
    setup_public_light(ufp)
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{light.mac}_light", config_entry=ufp.entry
    )
    issue_id = f"setting_mirror_deprecated_{light.mac}_light"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        breaks_in_ha_version=LIGHT_SETTING_MIRROR_BREAKS_IN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="setting_mirror_deprecated",
        translation_placeholders={
            "entity_id": mirror.entity_id,
            "replacement": "light.test_light",
            "items": "* `automation.gone`\n",
        },
    )

    await init_entry(hass, ufp, [light], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is not None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_migrate_light_setting_mirror_waits_for_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Automations loaded after the entry still get the repair."""
    setup_public_light(ufp)
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{light.mac}_light", config_entry=ufp.entry
    )
    hass.set_state(CoreState.starting)

    await init_entry(hass, ufp, [light], regenerate_ids=False)
    await _load_automation(hass, mirror.entity_id)
    assert not issue_registry.issues

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, f"setting_mirror_deprecated_{light.mac}_light"
    )


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
        pytest.param(Platform.BINARY_SENSOR, "light", "light", id="deprecation"),
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


async def test_migrate_light_setting_mirror_without_replacement(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Before the replacement exists there is nothing to point a repair at."""
    ufp.api.bootstrap.lights = {light.id: light}
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{light.mac}_light", config_entry=ufp.entry
    )
    await _load_automation(hass, mirror.entity_id)

    async_deprecate_light_setting_mirrors(hass, ufp.entry, ufp.api.bootstrap)

    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"setting_mirror_deprecated_{light.mac}_light"
        )
        is None
    )


@pytest.mark.parametrize(
    ("platform", "replacement_platform", "device", "key"),
    [
        pytest.param(
            Platform.BINARY_SENSOR,
            Platform.SWITCH,
            "light",
            "high_fps",
            id="camera_key_on_light",
        ),
        pytest.param(
            Platform.SENSOR,
            Platform.NUMBER,
            "doorbell",
            "sensitivity",
            id="light_key_on_camera",
        ),
    ],
)
async def test_migrate_setting_mirror_key_out_of_scope(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    light: Light,
    request: pytest.FixtureRequest,
    platform: Platform,
    replacement_platform: Platform,
    device: str,
    key: str,
) -> None:
    """A mirror key only counts on the device type it belongs to.

    A matching control is registered so only the scope can stop the repair.
    """
    setup_public_light(ufp)
    setup_public_camera(ufp)
    mac = request.getfixturevalue(device).mac
    unique_id = f"{mac}_{key}"
    entity_registry.async_get_or_create(
        replacement_platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    mirror = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [doorbell, light], regenerate_ids=False)

    assert (
        issue_registry.async_get_issue(DOMAIN, f"setting_mirror_deprecated_{unique_id}")
        is None
    )


@pytest.mark.parametrize(
    ("platform", "replacement_platform", "device", "key"),
    [
        pytest.param(
            Platform.BINARY_SENSOR,
            Platform.SWITCH,
            "doorbell",
            "high_fps",
            id="camera_key_on_camera",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            Platform.SWITCH,
            "doorbell",
            "status_light",
            id="shared_key_on_camera",
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            Platform.SWITCH,
            "light",
            "status_light",
            id="shared_key_on_light",
        ),
    ],
)
async def test_migrate_setting_mirror_key_in_scope(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    light: Light,
    request: pytest.FixtureRequest,
    platform: Platform,
    replacement_platform: Platform,
    device: str,
    key: str,
) -> None:
    """A mirror key on its own device type gets the repair."""
    setup_public_light(ufp)
    setup_public_camera(ufp)
    mac = request.getfixturevalue(device).mac
    unique_id = f"{mac}_{key}"
    entity_registry.async_get_or_create(
        replacement_platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    mirror = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [doorbell, light], regenerate_ids=False)

    assert issue_registry.async_get_issue(
        DOMAIN, f"setting_mirror_deprecated_{unique_id}"
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
        "platform",
        "key",
        "replacement_platform",
        "replacement_key",
        "translation_key",
    ),
    [
        *(
            pytest.param(
                Platform.BINARY_SENSOR,
                key,
                Platform.SWITCH,
                key,
                "setting_mirror_deprecated",
                id=key,
            )
            for key in _CAMERA_SWITCH_MIRRORS
        ),
        pytest.param(
            Platform.BINARY_SENSOR,
            "hdr_mode",
            Platform.SELECT,
            "hdr_mode",
            "setting_mirror_deprecated_hdr_mode",
            id="hdr_mode",
        ),
        pytest.param(
            Platform.SENSOR,
            "mic_level",
            Platform.NUMBER,
            "mic_level",
            "setting_mirror_deprecated_mic_level",
            id="mic_level",
        ),
        pytest.param(
            Platform.SENSOR,
            "doorbell_text",
            Platform.TEXT,
            "doorbell",
            "setting_mirror_deprecated_doorbell_text",
            id="doorbell_text",
        ),
    ],
)
async def test_migrate_camera_setting_mirror_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    replacement_platform: Platform,
    replacement_key: str,
    translation_key: str,
) -> None:
    """A used camera mirror gets a repair naming the control that replaces it."""
    # Every detection type, so each detection switch exists as a replacement.
    doorbell.feature_flags.smart_detect_types = [
        t for t in SmartDetectObjectType if t.audio_type is None
    ]
    doorbell.feature_flags.smart_detect_audio_types = list(SmartDetectAudioType)
    setup_public_camera(ufp)
    mirror = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"setting_mirror_deprecated_{doorbell.mac}_{key}"
    )
    assert issue is not None
    assert issue.translation_key == translation_key
    assert issue.breaks_in_ha_version == CAMERA_SETTING_MIRROR_BREAKS_IN
    replacement_id = entity_registry.async_get_entity_id(
        replacement_platform, DOMAIN, f"{doorbell.mac}_{replacement_key}"
    )
    assert replacement_id is not None
    assert issue.translation_placeholders["replacement"] == replacement_id


CAMERA_MAC = "AABBCCDDEE01"
LIGHT_MAC = "AABBCCDDEE02"
VIEWER_MAC = "AABBCCDDEE03"
SENSOR_MAC = "AABBCCDDEE04"
NVR_MAC = "AABBCCDDEE05"
CHIME_MAC = "AABBCCDDEE06"


def _private_only_bootstrap() -> Mock:
    """Return a bootstrap with one device of each model."""
    return Mock(
        nvr=Mock(mac=NVR_MAC),
        cameras={"camera": Mock(mac=CAMERA_MAC)},
        lights={"light": Mock(mac=LIGHT_MAC)},
        viewers={"viewer": Mock(mac=VIEWER_MAC)},
        sensors={"sensor": Mock(mac=SENSOR_MAC)},
        chimes={"chime": Mock(mac=CHIME_MAC)},
    )


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
async def test_deprecate_private_only_entity_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    mac: str,
    platform: Platform,
    key: str,
) -> None:
    """A used private-only entity gets a deprecation repair."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())

    issue = issue_registry.async_get_issue(
        DOMAIN, f"private_only_entity_deprecated_{platform}_{mac}_{key}"
    )
    assert issue is not None
    assert issue.translation_key == "private_only_entity_deprecated"
    assert issue.breaks_in_ha_version == "2027.1.0"
    assert issue.translation_placeholders["entity_id"] == entity.entity_id


@pytest.mark.parametrize(
    ("platform", "unique_id"),
    [
        pytest.param(Platform.SENSOR, f"{CAMERA_MAC}_ssh", id="key_on_other_platform"),
        pytest.param(
            Platform.SELECT, f"{CAMERA_MAC}_mount_type", id="key_of_other_model"
        ),
        pytest.param(
            Platform.SENSOR, f"{CAMERA_MAC}_x_voltage", id="key_inside_unique_id"
        ),
        pytest.param(Platform.SENSOR, "AABBCCDDEE99_voltage", id="unknown_device"),
    ],
)
async def test_deprecate_private_only_entity_not_matched(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    platform: Platform,
    unique_id: str,
) -> None:
    """Only the deprecated key on its platform and device model counts."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, unique_id, config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())

    assert not issue_registry.issues


async def test_deprecate_private_only_entity_shared_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """An unused entity does not clear the repair of its counterpart."""
    # The used entity comes first, so the unused one is scanned after it.
    used = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    await _load_automation(hass, used.entity_id)

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())

    assert issue_registry.async_get_issue(
        DOMAIN, f"private_only_entity_deprecated_binary_sensor_{CAMERA_MAC}_ssh"
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"private_only_entity_deprecated_switch_{CAMERA_MAC}_ssh"
        )
        is None
    )


async def test_deprecate_private_only_entity_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """A disabled entity is not active in any automation, so it gets no repair."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{CAMERA_MAC}_ssh",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    await _load_automation(hass, entity.entity_id)

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())

    assert not issue_registry.issues


async def test_deprecate_private_only_entity_repair_clears_when_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """The deprecation repair goes away once the last usage is gone."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    issue_id = f"private_only_entity_deprecated_switch_{CAMERA_MAC}_ssh"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        breaks_in_ha_version="2027.1.0",
        severity=ir.IssueSeverity.WARNING,
        translation_key="private_only_entity_deprecated",
        translation_placeholders={
            "entity_id": entity.entity_id,
            "items": "* `automation.gone`\n",
        },
    )

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())

    assert entity_registry.async_get(entity.entity_id) is not None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_deprecate_private_only_entity_waits_for_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """The scan runs once startup is done, when the automations are loaded."""
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)
    hass.set_state(CoreState.starting)

    async_deprecate_private_only_entities(hass, ufp.entry, _private_only_bootstrap())
    assert not issue_registry.issues

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, f"private_only_entity_deprecated_switch_{CAMERA_MAC}_ssh"
    )


async def test_deprecate_private_only_entities_on_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Setup raises the repair for a used private-only entity."""
    nvr_mac = ufp.api.bootstrap.nvr.mac
    entity = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{nvr_mac}_analytics_enabled",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [])

    assert issue_registry.async_get_issue(
        DOMAIN, f"private_only_entity_deprecated_switch_{nvr_mac}_analytics_enabled"
    )


async def test_is_new_private_only_entity(hass: HomeAssistant) -> None:
    """A deprecated entity that is not registered yet counts as new."""
    assert async_is_new_private_only_entity(hass, ModelType.CAMERA, CAMERA_MAC, "ssh")


@pytest.mark.parametrize(
    "platform",
    [
        pytest.param(Platform.SWITCH, id="same_platform"),
        pytest.param(Platform.BINARY_SENSOR, id="other_platform"),
    ],
)
async def test_is_new_private_only_entity_registered(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    platform: Platform,
) -> None:
    """An entity the user already has under the key is kept."""
    entity_registry.async_get_or_create(
        platform, DOMAIN, f"{CAMERA_MAC}_ssh", config_entry=ufp.entry
    )

    assert not async_is_new_private_only_entity(
        hass, ModelType.CAMERA, CAMERA_MAC, "ssh"
    )


@pytest.mark.parametrize(
    ("model", "key"),
    [
        pytest.param(ModelType.CAMERA, "status_light", id="key_not_deprecated"),
        pytest.param(ModelType.LINK_STATION, "uptime", id="model_without_deprecations"),
        pytest.param(None, "ssh", id="no_model"),
    ],
)
async def test_is_new_private_only_entity_not_deprecated(
    hass: HomeAssistant, model: ModelType | None, key: str
) -> None:
    """Entities that are not deprecated are never skipped."""
    assert not async_is_new_private_only_entity(hass, model, CAMERA_MAC, key)


async def test_private_only_entities_skipped_on_new_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A new install does not get the deprecated entities."""
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    nvr_mac = ufp.api.bootstrap.nvr.mac
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{doorbell.mac}_voltage"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, f"{nvr_mac}_insights_enabled"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{nvr_mac}_cpu_temperature"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{doorbell.mac}_uptime"
        )
        is None
    )
    assert entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{doorbell.mac}_status_light"
    )
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{nvr_mac}_storage_utilization"
    )
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{doorbell.mac}_wifi_signal"
    )


async def test_private_only_entities_kept_on_existing_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """An install that already has the deprecated entities keeps them working."""
    nvr_mac = ufp.api.bootstrap.nvr.mac
    kept = [
        entity_registry.async_get_or_create(
            platform, DOMAIN, unique_id, config_entry=ufp.entry
        )
        for platform, unique_id in (
            (Platform.SENSOR, f"{doorbell.mac}_voltage"),
            (Platform.SWITCH, f"{doorbell.mac}_ssh"),
            (Platform.SWITCH, f"{nvr_mac}_insights_enabled"),
            (Platform.SENSOR, f"{nvr_mac}_cpu_temperature"),
        )
    ]

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    for entity in kept:
        assert hass.states.get(entity.entity_id) is not None


RING_AND_MOTION_SENSORS = [
    pytest.param(
        Platform.BINARY_SENSOR,
        "doorbell",
        "doorbell",
        "doorbell_sensor_deprecated",
        id="doorbell_binary_sensor",
    ),
    pytest.param(
        Platform.SENSOR,
        "doorbell_last_trip_time",
        "doorbell",
        "last_event_sensor_deprecated",
        id="last_ring_sensor",
    ),
    pytest.param(
        Platform.SENSOR,
        "motion_last_trip_time",
        "motion_detection",
        "last_event_sensor_deprecated",
        id="last_motion_sensor",
    ),
]


@pytest.mark.parametrize(
    ("platform", "key", "replacement_key", "translation_key"),
    RING_AND_MOTION_SENSORS,
)
async def test_deprecate_ring_and_motion_sensor_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    replacement_key: str,
    translation_key: str,
) -> None:
    """A used ring or motion sensor gets a repair naming its event entity."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert hass.states.get(entity.entity_id) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"setting_mirror_deprecated_{doorbell.mac}_{key}"
    )
    assert issue is not None
    assert issue.translation_key == translation_key
    assert issue.breaks_in_ha_version == PRIVATE_ONLY_BREAKS_IN
    assert issue.translation_placeholders["entity_id"] == entity.entity_id
    replacement_id = entity_registry.async_get_entity_id(
        Platform.EVENT, DOMAIN, f"{doorbell.mac}_{replacement_key}"
    )
    assert replacement_id is not None
    assert issue.translation_placeholders["replacement"] == replacement_id


@pytest.mark.parametrize(
    ("platform", "key", "replacement_key", "translation_key"),
    RING_AND_MOTION_SENSORS,
)
async def test_deprecate_ring_and_motion_sensor_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    platform: Platform,
    key: str,
    replacement_key: str,
    translation_key: str,
) -> None:
    """An unused ring or motion sensor keeps working without a repair."""
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, f"{doorbell.mac}_{key}", config_entry=ufp.entry
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert hass.states.get(entity.entity_id) is not None
    assert not issue_registry.issues


async def test_deprecate_ring_and_motion_sensor_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A disabled sensor is not active in any automation, so it gets no repair."""
    entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{doorbell.mac}_motion_last_trip_time",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert not issue_registry.issues


async def test_deprecate_ring_and_motion_sensor_repair_clears_when_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """The deprecation repair goes away once the last usage is gone."""
    entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_doorbell",
        config_entry=ufp.entry,
    )
    issue_id = f"setting_mirror_deprecated_{doorbell.mac}_doorbell"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        breaks_in_ha_version=PRIVATE_ONLY_BREAKS_IN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="doorbell_sensor_deprecated",
        translation_placeholders={
            "entity_id": entity.entity_id,
            "replacement": "event.test_camera_doorbell",
            "items": "* `automation.gone`\n",
        },
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(entity.entity_id) is not None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_ring_and_motion_sensors_skipped_on_new_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A new install gets the event entities but not the deprecated sensors."""
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    for platform, key in (
        (Platform.BINARY_SENSOR, "doorbell"),
        (Platform.SENSOR, "doorbell_last_trip_time"),
        (Platform.SENSOR, "motion_last_trip_time"),
    ):
        assert (
            entity_registry.async_get_entity_id(
                platform, DOMAIN, f"{doorbell.mac}_{key}"
            )
            is None
        )
    for key in ("doorbell", "motion_detection"):
        assert entity_registry.async_get_entity_id(
            Platform.EVENT, DOMAIN, f"{doorbell.mac}_{key}"
        )
    assert entity_registry.async_get_entity_id(
        Platform.TEXT, DOMAIN, f"{doorbell.mac}_doorbell"
    )


@pytest.mark.parametrize(
    ("platform", "key", "expected"),
    [
        pytest.param(Platform.BINARY_SENSOR, "doorbell", True, id="deprecated"),
        pytest.param(Platform.TEXT, "doorbell", False, id="shared_key"),
        pytest.param(Platform.SENSOR, "last_ring", False, id="not_deprecated"),
    ],
)
async def test_is_new_ring_or_motion_sensor(
    hass: HomeAssistant, platform: Platform, key: str, expected: bool
) -> None:
    """Only a deprecated sensor on its own platform counts as new."""
    assert (
        async_is_new_ring_or_motion_sensor(hass, platform, CAMERA_MAC, key) is expected
    )


async def test_is_new_ring_or_motion_sensor_registered(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, ufp: MockUFPFixture
) -> None:
    """A sensor the user already has is kept."""
    entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR, DOMAIN, f"{CAMERA_MAC}_doorbell", config_entry=ufp.entry
    )

    assert not async_is_new_ring_or_motion_sensor(
        hass, Platform.BINARY_SENSOR, CAMERA_MAC, "doorbell"
    )
