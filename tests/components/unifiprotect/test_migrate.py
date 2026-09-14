"""Test the UniFi Protect setup flow."""

from unittest.mock import patch

from uiprotect.data import Camera, Sensor

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.migrate import (
    SENSE_SETTING_MIRROR_BREAKS_IN,
    async_deprecate_sense_setting_mirrors,
)
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .utils import MockUFPFixture, init_entry, setup_public_sensor

from tests.typing import WebSocketGenerator


async def test_deprecated_entity(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair does not exist by default (new installs)."""

    await init_entry(hass, ufp, [doorbell])

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def test_deprecated_entity_no_automations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell])

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


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


async def test_deprecate_entity_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, entry.entity_id)
    await init_entry(hass, ufp, [doorbell])

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={AUTOMATION_DOMAIN: []},
    ):
        await hass.services.async_call(AUTOMATION_DOMAIN, SERVICE_RELOAD, blocking=True)

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def _load_script(hass: HomeAssistant, entity_id: str):
    assert await async_setup_component(
        hass,
        SCRIPT_DOMAIN,
        {
            SCRIPT_DOMAIN: {
                "test": {
                    "sequence": {
                        "service": "test.script",
                        "data": {"entity_id": entity_id},
                    }
                }
            },
        },
    )


async def test_deprecate_entity_script(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )
    await _load_script(hass, entry.entity_id)
    await init_entry(hass, ufp, [doorbell])

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={SCRIPT_DOMAIN: {}},
    ):
        await hass.services.async_call(SCRIPT_DOMAIN, SERVICE_RELOAD, blocking=True)

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


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


async def test_migrate_package_binary_sensor_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """An unused package binary sensor is removed silently."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
        )
        is None
    )


async def test_migrate_sense_setting_mirrors_kept(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """The unused setting mirrors survive the deprecation without a repair."""
    existing = {
        (platform, key): entity_registry.async_get_or_create(
            platform,
            DOMAIN,
            f"{sensor_all.mac}_{key}",
            config_entry=ufp.entry,
        )
        for platform, key in (
            (Platform.BINARY_SENSOR, "motion_enabled"),
            (Platform.BINARY_SENSOR, "temperature"),
            (Platform.BINARY_SENSOR, "humidity"),
            (Platform.BINARY_SENSOR, "light"),
            (Platform.BINARY_SENSOR, "alarm"),
            (Platform.SENSOR, "sensitivity"),
        )
    }

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    for (platform, key), entity in existing.items():
        assert entity_registry.async_get(entity.entity_id) is not None, (
            f"{platform}.{key}"
        )
        assert (
            issue_registry.async_get_issue(
                DOMAIN, f"sense_setting_mirror_deprecated_{sensor_all.mac}_{key}"
            )
            is None
        )


async def test_migrate_sense_setting_mirror_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Deprecating a used setting mirror raises an actionable repair."""
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"sense_setting_mirror_deprecated_{sensor_all.mac}_alarm"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == SENSE_SETTING_MIRROR_BREAKS_IN
    assert issue.translation_placeholders["entity_id"] == mirror.entity_id
    replacement_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{sensor_all.mac}_alarm"
    )
    assert issue.translation_placeholders["replacement"] == replacement_id


async def test_migrate_sense_setting_mirror_repair_clears_when_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """The deprecation repair goes away once the last usage is gone.

    A removal repair has to persist, but the entity is still there, so the user
    can act on this one and it must not keep nagging afterwards.
    """
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp.entry,
    )
    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)
    assert entity_registry.async_get(mirror.entity_id) is not None

    # The repair a previous run raised while the mirror was still in use.
    issue_id = f"sense_setting_mirror_deprecated_{sensor_all.mac}_alarm"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        breaks_in_ha_version=SENSE_SETTING_MIRROR_BREAKS_IN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="sense_setting_mirror_deprecated",
        translation_placeholders={
            "entity_id": mirror.entity_id,
            "replacement": "switch.test_sensor_alarm_sound_detection",
            "items": "* `automation.gone`\n",
        },
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    async_deprecate_sense_setting_mirrors(hass, ufp.entry, ufp.api.bootstrap)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_migrate_sense_setting_mirror_in_use_no_replacement(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A device that cannot support the setting gets the no-replacement repair."""
    setup_public_sensor(ufp, capabilities=set())
    mirror = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_alarm",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, mirror.entity_id)

    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(mirror.entity_id) is not None
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, f"{sensor_all.mac}_alarm"
        )
        is None
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, f"sense_setting_mirror_deprecated_{sensor_all.mac}_alarm"
    )
    assert issue is not None
    assert issue.translation_key == "sense_setting_mirror_deprecated_no_replacement"
    assert issue.translation_placeholders["entity_id"] == mirror.entity_id
    assert "replacement" not in issue.translation_placeholders


async def test_migrate_sense_setting_keys_scoped_to_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    sensor_all: Sensor,
) -> None:
    """The deprecated keys are shared with camera and light, so scoping matters.

    ``motion_enabled`` and ``sensitivity`` also exist on cameras and lights, so a
    sensor has to be present for the migration to run at all and only the
    sensor's own mirror may be deprecated.
    """
    camera_entities = [
        entity_registry.async_get_or_create(
            platform,
            DOMAIN,
            f"{doorbell.mac}_{key}",
            config_entry=ufp.entry,
        )
        for platform, key in (
            (Platform.BINARY_SENSOR, "motion_enabled"),
            (Platform.SENSOR, "sensitivity"),
        )
    ]
    sensor_entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{sensor_all.mac}_motion_enabled",
        config_entry=ufp.entry,
    )

    # Both are used, so only the scoping decides which one gets a repair.
    await _load_automation(hass, sensor_entity.entity_id)
    for entity in camera_entities:
        await _load_automation(hass, entity.entity_id)

    await init_entry(hass, ufp, [doorbell, sensor_all], regenerate_ids=False)

    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"sense_setting_mirror_deprecated_{sensor_all.mac}_motion_enabled"
        )
        is not None
    )
    for entity in camera_entities:
        assert entity_registry.async_get(entity.entity_id) is not None
        assert (
            issue_registry.async_get_issue(
                DOMAIN, f"sense_setting_mirror_deprecated_{entity.unique_id}"
            )
            is None
        )


async def test_migrate_package_binary_sensor_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Removing a used package binary sensor raises an actionable repair."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, package.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == package.entity_id


async def test_migrate_package_binary_sensor_removed_disabled_not_repaired(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A disabled package binary sensor is removed without a repair even if referenced."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await _load_automation(hass, package.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
        )
        is None
    )
