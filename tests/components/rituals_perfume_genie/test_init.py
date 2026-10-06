"""Tests for the Rituals Perfume Genie integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from ritualsgenie import (
    RitualsGenieAuthenticationError,
    RitualsGenieConnectionError,
    RitualsGenieError,
    RitualsGenieRateLimitError,
)

from homeassistant.components.rituals_perfume_genie.const import ACCOUNT_HASH, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_TOKEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    init_integration,
    mock_client,
    mock_config_entry,
    mock_diffuser,
    mock_diffuser_v1_battery_cartridge,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_migration_v1_to_v2(
    hass: HomeAssistant,
    mock_rituals_client: AsyncMock,
    old_mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from V1 (account_hash) to V2 (credentials)."""
    old_mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert old_mock_config_entry.version == 2
    assert ACCOUNT_HASH not in old_mock_config_entry.data
    assert old_mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_rituals_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry setup when connection to Rituals is missing."""
    mock_config_entry.add_to_hass(hass)
    mock_rituals_client.hubs.side_effect = RitualsGenieConnectionError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_rituals_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry setup with invalid credentials starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    mock_rituals_client.hubs.side_effect = RitualsGenieAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    "exception",
    [
        RitualsGenieConnectionError,
        RitualsGenieError,
        RitualsGenieRateLimitError("Slow down", retry_after=60),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test entities become unavailable when updating fails."""
    config_entry = mock_config_entry(unique_id="id_123_update_failed")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])
    client.hubs.side_effect = exception

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_update_auth_failed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a reauth flow is started when the credentials stopped working."""
    config_entry = mock_config_entry(unique_id="id_123_update_auth_failed")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])
    client.hubs.side_effect = RitualsGenieAuthenticationError

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_config_entry_unload(hass: HomeAssistant) -> None:
    """Test the Rituals Perfume Genie configuration entry setup and unloading."""
    config_entry = mock_config_entry(unique_id="id_123_unload")
    await init_integration(hass, config_entry, [mock_diffuser(hublot="lot123")])

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_entity_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the migration of unique IDs on config entry setup."""
    config_entry = mock_config_entry(unique_id="binary_sensor_test_diffuser_v1")
    config_entry.add_to_hass(hass)

    # Pre-create old style unique IDs
    charging = entity_registry.async_get_or_create(
        "binary_sensor", DOMAIN, "lot123v1 Battery Charging", config_entry=config_entry
    )
    perfume_amount = entity_registry.async_get_or_create(
        "number", DOMAIN, "lot123v1 Perfume Amount", config_entry=config_entry
    )
    room_size = entity_registry.async_get_or_create(
        "select", DOMAIN, "lot123v1 Room Size", config_entry=config_entry
    )
    battery = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Battery", config_entry=config_entry
    )
    fill = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Fill", config_entry=config_entry
    )
    perfume = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Perfume", config_entry=config_entry
    )
    wifi = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "lot123v1 Wifi", config_entry=config_entry
    )
    switch = entity_registry.async_get_or_create(
        "switch", DOMAIN, "lot123v1", config_entry=config_entry
    )

    # Set up integration
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])

    # Check that old style unique IDs have been migrated
    entry = entity_registry.async_get(charging.entity_id)
    assert entry.unique_id == "lot123v1-charging"

    entry = entity_registry.async_get(perfume_amount.entity_id)
    assert entry.unique_id == "lot123v1-perfume_amount"

    entry = entity_registry.async_get(room_size.entity_id)
    assert entry.unique_id == "lot123v1-room_size_square_meter"

    entry = entity_registry.async_get(battery.entity_id)
    assert entry.unique_id == "lot123v1-battery_percentage"

    entry = entity_registry.async_get(fill.entity_id)
    assert entry.unique_id == "lot123v1-fill"

    entry = entity_registry.async_get(perfume.entity_id)
    assert entry.unique_id == "lot123v1-perfume"

    entry = entity_registry.async_get(wifi.entity_id)
    assert entry.unique_id == "lot123v1-wifi_percentage"

    entry = entity_registry.async_get(switch.entity_id)
    assert entry.unique_id == "lot123v1-is_on"


async def test_token_reused(hass: HomeAssistant) -> None:
    """Test a stored token is handed to the client, saving a login."""
    config_entry = mock_config_entry(unique_id="id_123_token_reused")
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TOKEN: "stored-token"}
    )

    with patch(
        "homeassistant.components.rituals_perfume_genie.RitualsGenie",
        return_value=mock_client([mock_diffuser("lot123")]),
    ) as client_class:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert client_class.call_args.kwargs["token"] == "stored-token"


async def test_token_stored(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a new token is stored in the config entry."""
    config_entry = mock_config_entry(unique_id="id_123_token_stored")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])

    assert config_entry.data[CONF_TOKEN] == "mock-token"

    client.token = "new-token"
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.data[CONF_TOKEN] == "new-token"
