"""Test the Portainer initial specific behavior."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import DockerContainer, EndpointStatus
from pyportainer.models.portainer import Endpoint
from pyportainer.models.stacks import Stack
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import DOMAIN, SUBENTRY_TYPE_ENVIRONMENT
from homeassistant.components.portainer.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import MOCK_TEST_CONFIG, TEST_INSTANCE_ID


async def _mock_duplicate_container_names(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    container_names: tuple[str, str] = ("alloy", "frost-eventlog"),
) -> None:
    """Mock two endpoints that contain containers with the same names."""
    endpoint_fixtures = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "endpoints.json", DOMAIN),
    )
    endpoints = []
    for endpoint_id, endpoint_name in ((1, "Unraid"), (3, "synology")):
        endpoint = dict(endpoint_fixtures[0])
        endpoint["Id"] = endpoint_id
        endpoint["Name"] = endpoint_name
        endpoint["Status"] = EndpointStatus.UP
        endpoints.append(Endpoint.from_dict(endpoint))
    mock_portainer_client.get_endpoints.return_value = endpoints

    container_fixtures = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "containers.json", DOMAIN),
    )
    containers = []
    for fixture, container_name in zip(
        container_fixtures[:2], container_names, strict=True
    ):
        container = dict(fixture)
        container["Names"] = [f"/{container_name}"]
        containers.append(DockerContainer.from_dict(container))
    mock_portainer_client.get_containers.return_value = containers


def _create_v5_config_entry() -> MockConfigEntry:
    """Create a v5 entry with subentries for both mocked endpoints."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Portainer test",
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        version=5,
        minor_version=3,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type=SUBENTRY_TYPE_ENVIRONMENT,
                title=endpoint_name,
                unique_id=endpoint_id,
            )
            for endpoint_id, endpoint_name in (("1", "Unraid"), ("3", "synology"))
        ],
    )


def _subentry_id(entry: MockConfigEntry, endpoint_id: str) -> str:
    """Return the subentry ID for a mocked endpoint."""
    return next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.unique_id == endpoint_id
    )


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (PortainerAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (PortainerConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (PortainerTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_portainer_client.portainer_system_status.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


async def test_migrations(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test migration from v1 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://test_host",
            CONF_API_KEY: "test_key",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    assert entry.version == 1
    assert CONF_VERIFY_SSL not in entry.data
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_HOST not in entry.data
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_URL] == "http://test_host"
    assert entry.data[CONF_API_TOKEN] == "test_key"
    assert entry.data[CONF_VERIFY_SSL] is True
    # Confirm we went through all current migrations
    assert entry.version == 5
    assert entry.minor_version == 4
    assert entry.unique_id == TEST_INSTANCE_ID


@pytest.mark.parametrize(
    ("identifier", "expected_result"),
    [
        pytest.param("1", False, id="present_endpoint"),
        pytest.param("1_practical_morse", False, id="present_container"),
        pytest.param("1_missing", True, id="stale_container"),
        pytest.param("5", True, id="stale_endpoint"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    identifier: str,
    expected_result: bool,
) -> None:
    """Test manually removing a stale device."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_{identifier}")},
    )

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device_entry.id)
    assert response["success"] == expected_result


async def test_migration_v3_to_v5(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from v3 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://test_host",
            CONF_API_TOKEN: "test_key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="1",
        version=3,
    )
    entry.add_to_hass(hass)
    assert entry.version == 3

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_endpoint_1")},
        name="Test Endpoint",
    )

    original_container_identifier = f"{entry.entry_id}_adguard"
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, original_container_identifier)},
        via_device_id=endpoint_device.id,
        model="Container",
        name="Test Container",
    )

    container_entity = entity_registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_adguard_container",
        config_entry=entry,
        device_id=container_device.id,
        original_name="Test Container Switch",
    )

    assert container_device.via_device_id == endpoint_device.id
    assert container_device.identifiers == {(DOMAIN, original_container_identifier)}
    assert container_entity.unique_id == f"{entry.entry_id}_adguard_container"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 5
    assert entry.minor_version == 4

    # Fetch again, to assert the new identifiers
    container_after = device_registry.async_get(container_device.id)
    entity_after = entity_registry.async_get(container_entity.entity_id)

    assert container_after.identifiers == {
        (DOMAIN, original_container_identifier),
        (DOMAIN, f"{entry.entry_id}_1_adguard"),
    }
    assert entity_after.unique_id == f"{entry.entry_id}_1_adguard_container"


async def test_migration_v5_1_to_v5_2(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of pre-subentry devices/entities into an environment subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://test_host",
            CONF_API_TOKEN: "test_key",
            CONF_VERIFY_SSL: True,
        },
        unique_id="1",
        version=5,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_1")},
        name="Test Endpoint",
    )
    # A device can carry identifiers from another domain if it was merged with
    # a device from a different integration; the migration must ignore those.
    device_registry.async_update_device(
        endpoint_device.id,
        new_identifiers=endpoint_device.identifiers | {("other_domain", "some_id")},
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_1_adguard")},
        via_device_id=endpoint_device.id,
        model="Container",
        name="Test Container",
    )

    container_entity = entity_registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_adguard_container",
        config_entry=entry,
        device_id=container_device.id,
        original_name="Test Container Switch",
    )

    endpoint_entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_1_api_version",
        config_entry=entry,
        device_id=endpoint_device.id,
        original_name="Test Endpoint API Version",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 4
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_ENVIRONMENT
    assert subentry.unique_id == "1"

    endpoint_after = device_registry.async_get(endpoint_device.id)
    container_after = device_registry.async_get(container_device.id)
    entity_after = entity_registry.async_get(container_entity.entity_id)
    endpoint_entity_after = entity_registry.async_get(endpoint_entity.entity_id)
    assert endpoint_after.config_subentry_id == subentry.subentry_id
    assert container_after.config_subentry_id == subentry.subentry_id
    assert entity_after.config_subentry_id == subentry.subentry_id
    assert entity_after.unique_id == f"{entry.entry_id}_1_adguard_container"
    assert endpoint_entity_after.config_subentry_id == subentry.subentry_id
    assert endpoint_entity_after.unique_id == f"{entry.entry_id}_1_api_version"


@pytest.mark.parametrize(
    ("unique_id_suffix", "translation_key", "disabled_by", "expected_disabled_by"),
    [
        pytest.param(
            "1_image_disk_usage_total_size",
            "image_disk_usage_total_size",
            None,
            er.RegistryEntryDisabler.INTEGRATION,
            id="endpoint_disk_space",
        ),
        pytest.param(
            "1_volume_myvolume_volume_size",
            "volume_size",
            None,
            er.RegistryEntryDisabler.INTEGRATION,
            id="volume_size",
        ),
        pytest.param(
            "1_api_version",
            "api_version",
            None,
            None,
            id="not_disk_space",
        ),
        pytest.param(
            "1_image_disk_usage_total_size",
            "image_disk_usage_total_size",
            er.RegistryEntryDisabler.USER,
            er.RegistryEntryDisabler.USER,
            id="user_disabled",
        ),
    ],
)
async def test_migration_v5_2_to_v5_3(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    unique_id_suffix: str,
    translation_key: str,
    disabled_by: er.RegistryEntryDisabler | None,
    expected_disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test migration disables the disk space sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TEST_CONFIG,
        unique_id=TEST_INSTANCE_ID,
        version=5,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_{unique_id_suffix}",
        config_entry=entry,
        translation_key=translation_key,
        disabled_by=disabled_by,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 4
    assert (entity_after := entity_registry.async_get(entity.entity_id))
    assert entity_after.disabled_by is expected_disabled_by


async def test_unload_entry(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    mock_portainer_watcher.stop.assert_called_once()


async def test_watcher_start_stop(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that watcher starts and stops on HA events."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    mock_portainer_watcher.start.assert_called_once()

    mock_portainer_watcher.stop.reset_mock()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_portainer_watcher.stop.assert_called_once()


async def test_migration_v4_to_v5(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test v4 config entry migration updates unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TEST_CONFIG,
        unique_id=MOCK_TEST_CONFIG[CONF_API_TOKEN],
        version=4,
    )
    entry.add_to_hass(hass)
    assert entry.version == 4
    assert entry.unique_id == MOCK_TEST_CONFIG[CONF_API_TOKEN]

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 5
    assert entry.minor_version == 4
    assert entry.unique_id == TEST_INSTANCE_ID


async def test_migration_v5_preserves_legacy_entity_owner(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the existing entity remains assigned to its original endpoint."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="synology",
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3_alloy")},
        via_device_id=endpoint_device.id,
        model="Container",
        name="alloy",
    )
    endpoint_aware_entity = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_3_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_device.id,
        original_name="Migrated container",
    )
    legacy_duplicate = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_device.id,
        original_name="Container",
    )
    entity_registry.async_update_entity(
        endpoint_aware_entity.entity_id,
        name="Canonical custom name",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 5
    assert entry.minor_version == 4
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{entry.entry_id}_3_alloy_container",
        )
        == endpoint_aware_entity.entity_id
    )
    canonical_entity = entity_registry.async_get(endpoint_aware_entity.entity_id)
    assert canonical_entity is not None
    assert canonical_entity.name == "Canonical custom name"
    assert entity_registry.async_get(legacy_duplicate.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{entry.entry_id}_1_alloy_container",
        )
        is not None
    )


async def test_migration_v5_uses_subentry_when_endpoint_ancestor_is_missing(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test endpoint ownership falls back to the container's subentry."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="synology",
    )
    stack_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3_stack")},
        via_device_id=endpoint_device.id,
        model="Stack",
        name="Stack",
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3_alloy")},
        via_device_id=stack_device.id,
        model="Container",
        name="alloy",
    )
    legacy_entity = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_device.id,
        original_name="Container",
    )
    device_registry.async_update_device(stack_device.id, via_device_id=None)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(legacy_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_3_alloy_container"
    assert migrated_entity.device_id == container_device.id


@pytest.mark.parametrize(
    "disabled_by",
    [None, er.RegistryEntryDisabler.USER],
    ids=("enabled", "disabled"),
)
async def test_migration_v5_preserves_legacy_entity(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test a legacy entity is migrated in place, including disabled entities."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="synology",
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3_alloy")},
        via_device_id=endpoint_device.id,
        model="Container",
        name="alloy",
    )
    legacy_entity = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_device.id,
        original_name="Container",
    )
    entity_registry.async_update_entity(
        legacy_entity.entity_id,
        name="Custom container name",
        disabled_by=disabled_by,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(legacy_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_3_alloy_container"
    assert migrated_entity.device_id == container_device.id
    assert migrated_entity.name == "Custom container name"
    assert migrated_entity.disabled_by is disabled_by

    other_endpoint_entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        DOMAIN,
        f"{entry.entry_id}_1_alloy_container",
    )
    assert other_endpoint_entity_id is not None
    assert other_endpoint_entity_id != legacy_entity.entity_id


async def test_migration_v5_uses_parent_endpoint_for_numeric_container_name(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a legacy device identifier cannot be mistaken for its endpoint."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="synology",
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={
            (DOMAIN, f"{entry.entry_id}_1_1"),
            (DOMAIN, f"{entry.entry_id}_3_1_1"),
        },
        via_device_id=endpoint_device.id,
        model="Container",
        name="1_1",
    )
    legacy_entity = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_1_1_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_device.id,
        original_name="Container",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(legacy_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_3_1_1_container"
    assert migrated_entity.device_id == container_device.id


async def test_migration_v5_skips_endpoint_aware_numeric_container_name(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test endpoint-aware IDs are not mistaken for legacy IDs."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "1"),
        identifiers={(DOMAIN, f"{entry.entry_id}_1")},
        name="Unraid",
    )
    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "1"),
        identifiers={(DOMAIN, f"{entry.entry_id}_1_1")},
        via_device_id=endpoint_device.id,
        model="Container",
        name="1",
    )
    endpoint_aware_entity = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_1_1_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "1"),
        device_id=container_device.id,
        original_name="Container",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(endpoint_aware_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_1_1_container"
    assert migrated_entity.device_id == container_device.id


async def test_migration_v5_avoids_cross_device_unique_id_conflicts(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test colliding legacy IDs are migrated without losing either entity."""
    await _mock_duplicate_container_names(
        hass,
        mock_portainer_client,
        container_names=("alloy", "1_alloy"),
    )
    entry = _create_v5_config_entry()
    entry.add_to_hass(hass)

    endpoint_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "1"),
        identifiers={(DOMAIN, f"{entry.entry_id}_1")},
        name="Unraid",
    )
    endpoint_3 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3")},
        name="synology",
    )
    container_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "1"),
        identifiers={(DOMAIN, f"{entry.entry_id}_1_alloy")},
        via_device_id=endpoint_1.id,
        model="Container",
        name="alloy",
    )
    container_3 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=_subentry_id(entry, "3"),
        identifiers={(DOMAIN, f"{entry.entry_id}_3_1_alloy")},
        via_device_id=endpoint_3.id,
        model="Container",
        name="1_alloy",
    )
    entity_1 = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "1"),
        device_id=container_1.id,
        original_name="Container 1",
    )
    entity_3 = entity_registry.async_get_or_create(
        domain=Platform.SWITCH,
        platform=DOMAIN,
        unique_id=f"{entry.entry_id}_1_alloy_container",
        config_entry=entry,
        config_subentry_id=_subentry_id(entry, "3"),
        device_id=container_3.id,
        original_name="Container 3",
    )
    entity_registry.async_update_entity(entity_1.entity_id, name="Custom 1")
    entity_registry.async_update_entity(entity_3.entity_id, name="Custom 3")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity_1 = entity_registry.async_get(entity_1.entity_id)
    migrated_entity_3 = entity_registry.async_get(entity_3.entity_id)
    assert migrated_entity_1 is not None
    assert migrated_entity_3 is not None
    assert migrated_entity_1.unique_id == f"{entry.entry_id}_1_alloy_container"
    assert migrated_entity_3.unique_id == f"{entry.entry_id}_3_1_alloy_container"
    assert migrated_entity_1.device_id == container_1.id
    assert migrated_entity_3.device_id == container_3.id
    assert migrated_entity_1.name == "Custom 1"
    assert migrated_entity_3.name == "Custom 3"


async def test_duplicate_container_names_across_endpoints(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test same-named containers on separate endpoints have distinct entities."""
    await _mock_duplicate_container_names(hass, mock_portainer_client)
    entry = _create_v5_config_entry()

    await setup_integration(hass, entry)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    entities_by_endpoint = {
        endpoint_id: {
            (
                entity.domain,
                entity.unique_id.removeprefix(f"{entry.entry_id}_{endpoint_id}_"),
            )
            for entity in entries
            if entity.unique_id.startswith(
                (
                    f"{entry.entry_id}_{endpoint_id}_alloy_",
                    f"{entry.entry_id}_{endpoint_id}_frost-eventlog_",
                )
            )
        }
        for endpoint_id in (1, 3)
    }

    assert entities_by_endpoint[1] == entities_by_endpoint[3]
    assert {domain for domain, _ in entities_by_endpoint[1]} == {
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.EVENT,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.UPDATE,
    }


@pytest.mark.parametrize(
    ("exception", "state", "reason"),
    [
        pytest.param(
            PortainerAuthenticationError,
            ConfigEntryState.MIGRATION_ERROR,
            "An error occurred while trying to authenticate",
            id="authentication_error",
        ),
        pytest.param(
            PortainerConnectionError,
            ConfigEntryState.SETUP_RETRY,
            "An error occurred while trying to connect to the Portainer instance",
            id="connection_error",
        ),
        pytest.param(
            PortainerTimeoutError,
            ConfigEntryState.SETUP_RETRY,
            "A timeout occurred while trying to connect to the Portainer instance",
            id="timeout_error",
        ),
        pytest.param(
            PortainerError,
            ConfigEntryState.MIGRATION_ERROR,
            "Failed to fetch the Portainer instance ID",
            id="portainer_error",
        ),
        pytest.param(
            Exception("Some other error"),
            ConfigEntryState.MIGRATION_ERROR,
            None,
            id="unexpected_error",
        ),
    ],
)
async def test_migration_v4_to_v5_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    exception: type[Exception],
    state: ConfigEntryState,
    reason: str | None,
) -> None:
    """Test v4 config entry migration updates unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TEST_CONFIG,
        unique_id=MOCK_TEST_CONFIG[CONF_API_TOKEN],
        version=4,
    )
    entry.add_to_hass(hass)
    assert entry.version == 4
    assert entry.unique_id == MOCK_TEST_CONFIG[CONF_API_TOKEN]

    mock_portainer_client.portainer_system_status.side_effect = exception

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is state
    assert entry.reason == reason
    assert entry.version == 4


async def test_device_registry(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are correctly registered."""
    await setup_integration(hass, mock_config_entry)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    # Sort by identifier to ensure consistent order in snapshot
    assert sorted(device_entries, key=lambda x: list(x.identifiers)[0][1]) == snapshot


async def test_container_stack_device_links(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that stack-linked containers are nested under the correct stack device."""
    await setup_integration(hass, mock_config_entry)

    endpoint_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1"), mock_config_entry.entry_id
    )
    assert endpoint_device is not None

    dashy_stack_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_stack_2"), mock_config_entry.entry_id
    )
    assert dashy_stack_device is not None
    assert dashy_stack_device.via_device_id == endpoint_device.id

    webstack_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_stack_1"), mock_config_entry.entry_id
    )
    assert webstack_device is not None
    assert webstack_device.via_device_id == endpoint_device.id

    swarm_container_device = device_registry.async_get_device_by_identifier(
        (
            DOMAIN,
            f"{mock_config_entry.entry_id}_1_dashy_dashy.1.qgza68hnz4n1qvyz3iohynx05",
        ),
        mock_config_entry.entry_id,
    )
    assert swarm_container_device is not None
    assert swarm_container_device.via_device_id == dashy_stack_device.id

    compose_container_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_serene_banach"),
        mock_config_entry.entry_id,
    )
    assert compose_container_device is not None
    assert compose_container_device.via_device_id == webstack_device.id

    standalone_container_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_focused_einstein"),
        mock_config_entry.entry_id,
    )

    assert standalone_container_device is not None
    assert standalone_container_device.via_device_id == endpoint_device.id


async def test_docker_system_df_refresh_runs_on_ha_start(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test docker system df coordinator refreshes DF data on HA start."""
    await setup_integration(hass, mock_config_entry)

    assert (
        state := hass.states.get("sensor.my_environment_image_disk_usage_total_size")
    )
    assert state.state != STATE_UNAVAILABLE


async def test_new_endpoint_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new endpoint creates entities after refresh."""
    mock_portainer_client.get_endpoints.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # Only the Portainer update exists without endpoints
    assert [entity.unique_id for entity in entities] == [
        f"{mock_config_entry.entry_id}_server_update"
    ]

    mock_portainer_client.get_endpoints.return_value = [
        Endpoint.from_dict(endpoint)
        for endpoint in cast(
            list[dict[str, Any]],
            await async_load_json_array_fixture(hass, "endpoints.json", DOMAIN),
        )
        if endpoint["Status"] == EndpointStatus.UP
    ]

    # Without entities nothing listens to the coordinator, so it wouldn't poll.
    mock_config_entry.runtime_data.async_add_listener(lambda: None)
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) > 0

    # The endpoint and its stacks are discovered together on this refresh, so
    # the stack device must resolve the freshly-created endpoint device as its
    # via device instead of racing its creation.
    endpoint_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1"), mock_config_entry.entry_id
    )
    assert endpoint_device is not None

    stack_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_stack_2"),
        mock_config_entry.entry_id,
    )
    assert stack_device is not None
    assert stack_device.via_device_id == endpoint_device.id


async def test_removed_endpoint_stops_event_listener(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_event_listeners: dict[int, MagicMock],
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed endpoint's Docker event listener is stopped and dropped."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert 1 in coordinator._event_listeners

    mock_portainer_client.get_endpoints.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_event_listeners[1].stop.assert_called_once()
    assert 1 not in coordinator._event_listeners


async def test_new_container_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new container creates entities after refresh."""
    mock_portainer_client.get_containers.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_portainer_client.get_containers.return_value = [
        DockerContainer.from_dict(container)
        for container in cast(
            list[dict[str, Any]],
            await async_load_json_array_fixture(hass, "containers.json", DOMAIN),
        )
        if "/focused_einstein" in container["Names"]
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) > len(entities)


async def test_swarm_stacks_fetched_by_swarm_id(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Swarm manager calls get_stacks with both IDs."""
    await setup_integration(hass, mock_config_entry)

    calls = mock_portainer_client.get_stacks.call_args_list
    # Expect exactly two calls: one by endpoint_id, one by swarm_id
    assert len(calls) == 2
    assert calls[0].kwargs == {"endpoint_id": 1}
    assert calls[1].kwargs == {"endpoint_id": 1, "swarm_id": "swarm-cluster-id"}


async def test_new_stack_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new stack creates entities after refresh."""
    mock_portainer_client.get_stacks.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_portainer_client.get_stacks.return_value = [
        Stack.from_dict(stack)
        for stack in cast(
            list[dict[str, Any]],
            await async_load_json_array_fixture(hass, "stacks.json", DOMAIN),
        )
        if stack["Name"] == "webstack"
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) > len(entities)


async def test_stack_recreated_with_new_id(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stack recreated with the same name but a new ID re-registers its device.

    The stack device identifier and a container's via device are keyed by the stack
    ID, so a stack recreated with a new ID must be detected as new and its device
    registered before a container in it resolves the stack as its via device. Tracking
    only the name would skip registration and the via device lookup would then raise,
    aborting the refresh.
    """
    await setup_integration(hass, mock_config_entry)

    endpoint_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1"), mock_config_entry.entry_id
    )
    assert endpoint_device is not None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{mock_config_entry.entry_id}_1_stack_1"),
            mock_config_entry.entry_id,
        )
        is not None
    )

    stacks = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "stacks.json", DOMAIN),
    )
    for stack in stacks:
        if stack["Name"] == "webstack":
            stack["Id"] = 99
    mock_portainer_client.get_stacks.return_value = [
        Stack.from_dict(stack) for stack in stacks
    ]

    containers = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "containers.json", DOMAIN),
    )
    new_container = {
        **next(c for c in containers if c["Names"] == ["/serene_banach"]),
        "Names": ["/brave_newton"],
        "Id": "cc97facfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf",
    }
    mock_portainer_client.get_containers.return_value = [
        DockerContainer.from_dict(container)
        for container in (*containers, new_container)
    ]

    coordinator = mock_config_entry.runtime_data
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success

    new_stack_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_stack_99"),
        mock_config_entry.entry_id,
    )
    assert new_stack_device is not None
    assert new_stack_device.via_device_id == endpoint_device.id

    new_container_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{mock_config_entry.entry_id}_1_brave_newton"),
        mock_config_entry.entry_id,
    )
    assert new_container_device is not None
    assert new_container_device.via_device_id == new_stack_device.id
