"""Test HomematicIP Cloud setup process."""

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homematicip.exceptions.connection_exceptions import HmipConnectionError
import pytest

from homeassistant.components.homematicip_cloud import async_migrate_entry
from homeassistant.components.homematicip_cloud.const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.components.homematicip_cloud.migration import (
    UNIQUE_ID_MIGRATION_MAP,
    _migrate_unique_id,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .helper import HomeFactory

from tests.common import MockConfigEntry


async def test_config_with_accesspoint_passed_to_config_entry(
    hass: HomeAssistant, mock_connection, simple_mock_home
) -> None:
    """Test that config for a accesspoint are loaded via config entry."""

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }
    # no config_entry exists
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: entry_config})

    # config_entry created for access point
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # defined access_point created for config_entry
    assert isinstance(config_entries[0].runtime_data, HomematicipHAP)


async def test_config_already_registered_not_passed_to_config_entry(
    hass: HomeAssistant, simple_mock_home
) -> None:
    """Test that an already registered accesspoint does not get imported."""

    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    # one config_entry exists
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty has no unique_id
    assert not config_entries[0].unique_id

    entry_config = {
        CONF_ACCESSPOINT: "ABC123",
        CONF_AUTHTOKEN: "123",
        CONF_NAME: "name",
    }

    with patch(
        "homeassistant.components.homematicip_cloud.hap.HomematicipHAP.async_connect",
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: entry_config})

    # no new config_entry created / still one config_entry
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].data == {
        "authtoken": "123",
        "hapid": "ABC123",
        "name": "name",
    }
    # config_enty updated with unique_id
    assert config_entries[0].unique_id == "ABC123"


async def test_load_entry_fails_due_to_connection_error(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, mock_connection_init
) -> None:
    """Test load entry fails due to connection error."""
    hmip_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=HmipConnectionError,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    assert hmip_config_entry.runtime_data
    assert hmip_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_entry_fails_due_to_generic_exception(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry
) -> None:
    """Test load entry fails due to generic exception."""
    hmip_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    assert hmip_config_entry.runtime_data
    assert hmip_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test being able to unload an entry."""
    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        assert await async_setup_component(hass, DOMAIN, {})

    assert mock_hap.return_value.mock_calls[0][0] == "async_setup"

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].runtime_data
    assert config_entries[0].state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(config_entries[0].entry_id)
    assert config_entries[0].state is ConfigEntryState.NOT_LOADED


async def test_hmip_dump_hap_config_services(
    hass: HomeAssistant, mock_hap_with_service
) -> None:
    """Test dump configuration services."""

    with patch("pathlib.Path.write_text", return_value=Mock()) as write_mock:
        await hass.services.async_call(
            "homematicip_cloud", "dump_hap_config", {"anonymize": True}, blocking=True
        )
        home = mock_hap_with_service.home
        assert home.mock_calls[-1][0] == "download_configuration_async"
        assert home.mock_calls
        assert write_mock.mock_calls


async def test_setup_services(hass: HomeAssistant) -> None:
    """Test setup services."""
    mock_config = {HMIPC_AUTHTOKEN: "123", HMIPC_HAPID: "ABC123", HMIPC_NAME: "name"}
    MockConfigEntry(domain=DOMAIN, data=mock_config).add_to_hass(hass)

    with patch("homeassistant.components.homematicip_cloud.HomematicipHAP") as mock_hap:
        instance = mock_hap.return_value
        instance.async_setup = AsyncMock(return_value=True)
        instance.home.id = "1"
        instance.home.modelType = "mock-type"
        instance.home.name = "mock-name"
        instance.home.label = "mock-label"
        instance.home.currentAPVersion = "mock-ap-version"
        instance.async_reset = AsyncMock(return_value=True)

        assert await async_setup_component(hass, DOMAIN, {})

    # Check services are created
    hmipc_services = hass.services.async_services()[DOMAIN]
    assert len(hmipc_services) == 9

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1

    await hass.config_entries.async_unload(config_entries[0].entry_id)


# --- Unique ID migration tests ---


@pytest.fixture
def mock_config_entry_v1(hass: HomeAssistant) -> MockConfigEntry:
    """Create a v1 config entry for migration testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "token", HMIPC_NAME: ""},
        version=1,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    ("platform", "old_unique_id", "new_unique_id"),
    [
        (
            "binary_sensor",
            "HomematicipMotionDetector_3014F711ABCD",
            "3014F711ABCD_1_motion",
        ),
        (
            "switch",
            "HomematicipMultiSwitch_Channel3_3014F711ABCD",
            "3014F711ABCD_3_switch",
        ),
        (
            "light",
            "HomematicipNotificationLight_Top_3014F711ABCD",
            "3014F711ABCD_2_notification_light",
        ),
        ("climate", "HomematicipHeatingGroup_UUID-GROUP-123", "UUID-GROUP-123_climate"),
    ],
    ids=["single_channel", "multi_channel", "notification_light", "group"],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    platform: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique_id migration for different entity types."""
    entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        old_unique_id,
        config_entry=mock_config_entry_v1,
    )

    result = await async_migrate_entry(hass, mock_config_entry_v1)

    assert result is True
    assert mock_config_entry_v1.version == 2
    assert entity_registry.async_get_entity_id(platform, DOMAIN, new_unique_id)


async def test_migrate_stable_unique_id_skipped(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a non-class-name unique_id is silently skipped and preserved."""
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "HomematicipFutureEntity_3014F711ABCD",
        config_entry=mock_config_entry_v1,
    )

    result = await async_migrate_entry(hass, mock_config_entry_v1)

    assert result is True
    assert mock_config_entry_v1.version == 2
    # Unknown prefix is not a known class name, so it's treated as already
    # stable and skipped silently (no warning, just debug).
    assert "already stable format" in caplog.text
    # Old unique_id is preserved (not migrated)
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "HomematicipFutureEntity_3014F711ABCD"
    )


async def test_migrate_already_v2_is_noop(hass: HomeAssistant) -> None:
    """Test that a v2 config entry is a no-op."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "token", HMIPC_NAME: ""},
        version=2,
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)

    assert result is True
    assert entry.version == 2


async def test_migrate_battery_sensor(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration of battery sensor (channel 0)."""
    # Battery entity must be linked to a device, otherwise it's treated
    # as an obsolete access point battery entity and removed.
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "3014F711ABCD")},
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "HomematicipBatterySensor_3014F711ABCD",
        config_entry=mock_config_entry_v1,
        device_id=device_entry.id,
    )

    result = await async_migrate_entry(hass, mock_config_entry_v1)

    assert result is True
    assert mock_config_entry_v1.version == 2
    assert entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "3014F711ABCD_0_battery"
    )


async def test_migrate_removes_obsolete_access_point_battery_sensor(
    hass: HomeAssistant,
    mock_config_entry_v1: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Remove obsolete access point battery entity but keep real device battery sensors."""

    # Obsolete access point battery entity: legacy unique_id, no linked device.
    obsolete_entity_id = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "HomematicipBatterySensor_ABC123",
        config_entry=mock_config_entry_v1,
    ).entity_id

    # Real device battery entity: same legacy class prefix, but attached to a device.
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_v1.entry_id,
        identifiers={(DOMAIN, "3014F711ABCD")},
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "HomematicipBatterySensor_3014F711ABCD",
        config_entry=mock_config_entry_v1,
        device_id=device_entry.id,
    )

    result = await async_migrate_entry(hass, mock_config_entry_v1)

    assert result is True
    assert mock_config_entry_v1.version == 2
    assert entity_registry.async_get(obsolete_entity_id) is None
    assert entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "3014F711ABCD_0_battery"
    )


async def test_migrate_unique_id_collision_detection() -> None:
    """Test that different classes produce distinct unique_ids for the same device."""
    device_id = "3014F711ABCD"
    temp_uid = _migrate_unique_id(f"HomematicipTemperatureSensor_{device_id}")
    humidity_uid = _migrate_unique_id(f"HomematicipHumiditySensor_{device_id}")

    assert temp_uid is not None
    assert humidity_uid is not None
    assert temp_uid != humidity_uid
    assert temp_uid == f"{device_id}_1_temperature"
    assert humidity_uid == f"{device_id}_1_humidity"


def test_migration_map_completeness() -> None:
    """Verify every entity class has a migration map entry."""
    integration_path = Path(__file__).parents[3] / (
        "homeassistant/components/homematicip_cloud"
    )
    assert integration_path.is_dir(), f"Integration path not found: {integration_path}"
    platform_files = [
        "binary_sensor.py",
        "sensor.py",
        "light.py",
        "switch.py",
        "cover.py",
        "climate.py",
        "weather.py",
        "valve.py",
        "lock.py",
        "button.py",
        "event.py",
        "alarm_control_panel.py",
        "siren.py",
    ]
    # Classes excluded from the migration map:
    # - Abstract bases that never produce entities directly
    # - Dataclass descriptors (not entity classes)
    # - HmipSmokeDetectorSensor uses a custom unique_id format
    #   ({device_id}_{description_key}) that is already stable
    excluded_classes = {
        "HomematicipGenericEntity",
        "HomematicipBaseActionSensor",
        "HmipEsiSensorEntity",
        "HmipSmokeDetectorSensorDescription",
        "HmipEventEntityDescription",
        "HmipSmokeDetectorSensor",
    }

    entity_classes: set[str] = set()
    for filename in platform_files:
        filepath = integration_path / filename
        assert filepath.exists(), f"Platform file not found: {filepath}"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name not in excluded_classes:
                entity_classes.add(node.name)

    missing = entity_classes - set(UNIQUE_ID_MIGRATION_MAP.keys())
    assert not missing, (
        f"Entity classes missing from UNIQUE_ID_MIGRATION_MAP: {missing}"
    )


async def test_unique_id_migration_round_trip(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
) -> None:
    """Verify that migrating old-format unique_ids produces the runtime unique_ids.

    This catches mismatches between the migration map (channel/feature_id) and
    the actual entity __init__ parameters. For example, if the migration map
    says channel=1 for BatterySensor but the entity uses channel=0, this test
    will fail.
    """
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        extra_devices=[full_flush_lock_controller_device_data],
    )

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_hap.config_entry.entry_id
    )

    # Collect all runtime unique_ids
    runtime_unique_ids = {entry.unique_id for entry in entries}
    assert runtime_unique_ids, "No entities found after setup"

    # Build a reverse index: for each migration map class, record what old-format
    # unique_ids would look like and what they migrate to.
    # Then check that every migrated result matches a runtime unique_id.
    matched_classes: set[str] = set()
    mismatches: list[str] = []

    for class_name, config in UNIQUE_ID_MIGRATION_MAP.items():
        # For each runtime unique_id, check if this class could produce it
        for runtime_uid in runtime_unique_ids:
            if config.is_group:
                # Group format: {device_id}_{feature_id}
                # device_id may contain underscores, feature_id may contain underscores
                if not runtime_uid.endswith(f"_{config.feature_id}"):
                    continue
                device_id = runtime_uid[: -(len(config.feature_id) + 1)]
                # Construct old-format: {ClassName}_{device_id}
                old_uid = f"{class_name}_{device_id}"
            else:
                # Device format: {device_id}_{channel}_{feature_id}
                if not runtime_uid.endswith(f"_{config.feature_id}"):
                    continue
                if config.channel is not None:
                    # Single-channel: known fixed channel
                    suffix = f"_{config.channel}_{config.feature_id}"
                    if not runtime_uid.endswith(suffix):
                        continue
                    device_id = runtime_uid[: -len(suffix)]
                    old_uid = f"{class_name}_{device_id}"
                else:
                    # Multi-channel: parse channel from runtime unique_id
                    # Runtime: {device_id}_{channel}_{feature_id}
                    # Old: {ClassName}_Channel{N}_{device_id}
                    prefix = runtime_uid[: -(len(config.feature_id) + 1)]
                    # prefix is now {device_id}_{channel}
                    last_underscore = prefix.rfind("_")
                    if last_underscore == -1:
                        continue
                    channel_str = prefix[last_underscore + 1 :]
                    if not channel_str.isdigit():
                        continue
                    device_id = prefix[:last_underscore]
                    old_uid = f"{class_name}_Channel{channel_str}_{device_id}"

            # Migrate and verify
            migrated = _migrate_unique_id(old_uid)
            if migrated == runtime_uid:
                matched_classes.add(class_name)
            else:
                mismatches.append(
                    f"{class_name}: old='{old_uid}' -> migrated='{migrated}'"
                    f" != runtime='{runtime_uid}'"
                )

    assert not mismatches, "Migration round-trip mismatches:\n" + "\n".join(mismatches)
    # Ensure we actually tested a meaningful number of classes
    assert len(matched_classes) > 10, (
        f"Only matched {len(matched_classes)} classes: {sorted(matched_classes)}"
    )
