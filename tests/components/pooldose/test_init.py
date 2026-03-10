"""Test the PoolDose integration initialization."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import RequestStatus

from tests.common import MockConfigEntry


async def test_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device({(DOMAIN, "TEST123456789")})

    assert device is not None
    assert device == snapshot


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_coordinator_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test setup failure when coordinator first refresh fails."""
    mock_config_entry.add_to_hass(hass)
    mock_pooldose_client.instant_values_structured.side_effect = Exception(
        "API communication failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "status",
    [
        RequestStatus.HOST_UNREACHABLE,
        RequestStatus.PARAMS_FETCH_FAILED,
        RequestStatus.API_VERSION_UNSUPPORTED,
        RequestStatus.NO_DATA,
        RequestStatus.UNKNOWN_ERROR,
    ],
)
async def test_setup_entry_various_client_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    status: RequestStatus,
) -> None:
    """Test setup fails with various client error statuses."""
    mock_pooldose_client.connect.return_value = RequestStatus.HOST_UNREACHABLE
    mock_pooldose_client.is_connected = False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError("Connection timeout"),
        OSError("Network error"),
    ],
)
async def test_setup_entry_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test setup failure when client connection times out."""
    mock_pooldose_client.connect.side_effect = exception
    mock_pooldose_client.is_connected = False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entity_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_v1_1: MockConfigEntry,
) -> None:
    """Test migration of entity unique IDs."""
    mock_config_entry_v1_1.add_to_hass(hass)

    # Create entities with old unique ID format
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "TEST123456789_ofa_orp_value",
        config_entry=mock_config_entry_v1_1,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "TEST123456789_ofa_ph_value",
        config_entry=mock_config_entry_v1_1,
    )
    # Create entity with correct unique ID that should not be changed
    unchanged_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "TEST123456789_orp",
        config_entry=mock_config_entry_v1_1,
    )

    assert mock_config_entry_v1_1.version == 1
    assert mock_config_entry_v1_1.minor_version == 1

    # Setup the integration - this will trigger migration
    await hass.config_entries.async_setup(mock_config_entry_v1_1.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry version was updated from 1.1 to 1.2
    assert mock_config_entry_v1_1.version == 1
    assert mock_config_entry_v1_1.minor_version == 2

    # Verify the entities have been migrated
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST123456789_ofa_orp_time"
    )
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST123456789_ofa_ph_time"
    )

    # Verify old unique IDs no longer exist
    assert not entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST123456789_ofa_orp_value"
    )
    assert not entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST123456789_ofa_ph_value"
    )

    # Verify entity that didn't need migration is unchanged
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "TEST123456789_orp")
        == unchanged_entity.entity_id
    )
