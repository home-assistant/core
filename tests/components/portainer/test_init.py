"""Test the Portainer initial specific behavior."""

from unittest.mock import AsyncMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import DockerContainer
from pyportainer.models.portainer import Endpoint
from pyportainer.models.stacks import Stack
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import MOCK_TEST_CONFIG, TEST_INSTANCE_ID

from tests.common import MockConfigEntry, async_load_json_array_fixture
from tests.typing import WebSocketGenerator


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
    mock_portainer_client.get_endpoints.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


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
    assert entry.unique_id == TEST_INSTANCE_ID


@pytest.mark.parametrize(
    ("container_id", "expected_result"),
    [("1", False), ("5", True)],
    ids=("Present container", "Stale container"),
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    container_id: str,
    expected_result: bool,
) -> None:
    """Test manually removing a stale device."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_{container_id}")},
    )

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
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
        via_device=(DOMAIN, f"{entry.entry_id}_endpoint_1"),
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

    # Fetch again, to assert the new identifiers
    container_after = device_registry.async_get(container_device.id)
    entity_after = entity_registry.async_get(container_entity.entity_id)

    assert container_after.identifiers == {
        (DOMAIN, original_container_identifier),
        (DOMAIN, f"{entry.entry_id}_1_adguard"),
    }
    assert entity_after.unique_id == f"{entry.entry_id}_1_adguard_container"


async def test_migration_v4_to_v5(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
) -> None:
    """Test migration from v4 config entry updates unique_id to Portainer instance ID."""
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
    assert entry.unique_id == TEST_INSTANCE_ID


@pytest.mark.parametrize(
    ("exception"),
    [
        (PortainerAuthenticationError),
        (PortainerConnectionError),
        (PortainerTimeoutError),
        (Exception("Some other error")),
    ],
)
async def test_migration_v4_to_v5_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    exception: type[Exception],
) -> None:
    """Test migration from v4 config entry updates unique_id to Portainer instance ID."""
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

    assert entry.state == ConfigEntryState.MIGRATION_ERROR


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
    assert device_entries == snapshot


async def test_container_stack_device_links(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that stack-linked containers are nested under the correct stack device."""
    await setup_integration(hass, mock_config_entry)

    endpoint_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_1")}
    )
    assert endpoint_device is not None

    dashy_stack_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_1_stack_2")}
    )
    assert dashy_stack_device is not None
    assert dashy_stack_device.via_device_id == endpoint_device.id

    webstack_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_1_stack_1")}
    )
    assert webstack_device is not None
    assert webstack_device.via_device_id == endpoint_device.id

    swarm_container_device = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                f"{mock_config_entry.entry_id}_1_dashy_dashy.1.qgza68hnz4n1qvyz3iohynx05",
            )
        }
    )
    assert swarm_container_device is not None
    assert swarm_container_device.via_device_id == dashy_stack_device.id

    compose_container_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_1_serene_banach")}
    )
    assert compose_container_device is not None
    assert compose_container_device.via_device_id == webstack_device.id

    standalone_container_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_1_focused_einstein")}
    )

    assert standalone_container_device is not None
    assert standalone_container_device.via_device_id == endpoint_device.id


async def test_new_endpoint_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a new endpoint appearing in a subsequent refresh fires the callback and creates entities."""
    mock_portainer_client.get_endpoints.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 0

    mock_portainer_client.get_endpoints.return_value = [
        Endpoint.from_dict(endpoint)
        for endpoint in await async_load_json_array_fixture(
            hass, "endpoints.json", DOMAIN
        )
        if endpoint["Status"] == 1
    ]

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) > 0


async def test_new_container_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a new container appearing in a subsequent refresh fires the callback and creates entities."""
    mock_portainer_client.get_containers.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_portainer_client.get_containers.return_value = [
        DockerContainer.from_dict(container)
        for container in await async_load_json_array_fixture(
            hass, "containers.json", DOMAIN
        )
        if "/focused_einstein" in container["Names"]
    ]

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) > len(entities)


async def test_new_stack_callback(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a new stack appearing in a subsequent refresh fires the callback and creates entities."""
    mock_portainer_client.get_stacks.return_value = []
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_portainer_client.get_stacks.return_value = [
        Stack.from_dict(stack)
        for stack in await async_load_json_array_fixture(hass, "stacks.json", DOMAIN)
        if stack["Name"] == "webstack"
    ]

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) > len(entities)
