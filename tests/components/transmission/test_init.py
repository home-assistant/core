"""Tests for Transmission init."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.transmission.const import (
    DEFAULT_PATH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PATH, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG_DATA_VERSION_1_1, OLD_MOCK_CONFIG_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_flow_entry_migrate_1_1_to_1_2(
    hass: HomeAssistant,
) -> None:
    """Test that config flow entry is migrated correctly from v1.1 to v1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA_VERSION_1_1,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Test that config entry is at the current version.
    assert entry.version == 1
    assert entry.minor_version == 2

    assert entry.data[CONF_SSL] == DEFAULT_SSL
    assert entry.data[CONF_PATH] == DEFAULT_PATH


async def test_setup_failed_connection_error(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration failed due to connection error."""
    mock_config_entry.add_to_hass(hass)

    mock_transmission_client.side_effect = TransmissionConnectError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failed_auth_error(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration failed due to invalid credentials error."""
    mock_config_entry.add_to_hass(hass)

    mock_transmission_client.side_effect = TransmissionAuthError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_failed_unexpected_error(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration failed due to unexpected error."""
    mock_config_entry.add_to_hass(hass)

    mock_transmission_client.side_effect = TransmissionError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("domain", "old_unique_id", "new_unique_id"),
    [
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Down Speed", "1234-download"),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Up Speed", "1234-upload"),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Status", "1234-status"),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Active Torrents",
            "1234-active_torrents",
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Paused Torrents",
            "1234-paused_torrents",
        ),
        (SENSOR_DOMAIN, "0.0.0.0-Transmission Total Torrents", "1234-total_torrents"),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Completed Torrents",
            "1234-completed_torrents",
        ),
        (
            SENSOR_DOMAIN,
            "0.0.0.0-Transmission Started Torrents",
            "1234-started_torrents",
        ),
        # no change on correct sensor unique id
        (SENSOR_DOMAIN, "1234-started_torrents", "1234-started_torrents"),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Switch", "1234-on_off"),
        (SWITCH_DOMAIN, "0.0.0.0-Transmission Turtle Mode", "1234-turtle_mode"),
        # no change on correct switch unique id
        (SWITCH_DOMAIN, "1234-turtle_mode", "1234-turtle_mode"),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    domain: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test unique id migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=OLD_MOCK_CONFIG_DATA, entry_id="1234")
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id=f"my_{domain}",
        disabled_by=None,
        domain=domain,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(entity.entity_id)

    assert migrated_entity
    assert migrated_entity.unique_id == new_unique_id


async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors go unavailable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Make the coordinator fail on next update
    client = mock_transmission_client.return_value
    client.session_stats.side_effect = TransmissionError("Connection failed")

    # Trigger an update to make entities unavailable
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify entities are unavailable
    state = hass.states.get("sensor.transmission_status")
    assert state is not None
    assert state.state == "unavailable"
