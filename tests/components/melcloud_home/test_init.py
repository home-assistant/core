"""Test the MELCloud Home integration init behavior."""

from unittest.mock import AsyncMock

from aiomelcloudhome import UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeNotFoundError,
    MelCloudHomeTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.components.melcloud_home.coordinator import (
    TELEMETRY_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import MOCK_USER_INPUT

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "setup_state", "translation_key"),
    [
        pytest.param(
            MelCloudHomeAuthenticationError("bad creds"),
            ConfigEntryState.SETUP_ERROR,
            "invalid_auth",
            id="auth",
        ),
        pytest.param(
            MelCloudHomeConnectionError("cannot connect"),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            id="connection",
        ),
        pytest.param(
            MelCloudHomeTimeoutError("timeout"),
            ConfigEntryState.SETUP_RETRY,
            "timeout_connect",
            id="timeout",
        ),
        pytest.param(
            MelCloudHomeNotFoundError("not found"),
            ConfigEntryState.SETUP_RETRY,
            "api_error",
            id="api_error",
        ),
    ],
)
async def test_entry_setup_retry_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    exception: Exception,
    setup_state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test setup retries when initial coordinator refresh fails."""
    mock_melcloud_client.get_context.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is setup_state
    assert mock_config_entry.error_reason_translation_key == translation_key


async def test_new_ata_unit_callback(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new ATA units discovered on coordinator refresh create climate entities."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToAirUnits": []} for building in fixture["buildings"]
            ],
        }
    )
    await setup_integration(hass, mock_config_entry)
    ata_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "living_room" in entity.entity_id
    ]
    assert not ata_entities

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(fixture)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    ata_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "living_room" in entity.entity_id
    ]
    assert ata_entities


@pytest.mark.parametrize(
    (
        "removed_units_key",
        "removed_unit_id",
        "removed_entity_id",
        "kept_unit_id",
        "kept_entity_id",
    ),
    [
        pytest.param(
            "airToAirUnits",
            "ata-unit-uuid-1",
            "climate.living_room_ac",
            "atw-unit-uuid-1",
            "climate.heat_pump_zone_1",
            id="ata",
        ),
        pytest.param(
            "airToWaterUnits",
            "atw-unit-uuid-1",
            "climate.heat_pump_zone_1",
            "ata-unit-uuid-1",
            "climate.living_room_ac",
            id="atw",
        ),
    ],
)
async def test_stale_devices_removed(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    removed_units_key: str,
    removed_unit_id: str,
    removed_entity_id: str,
    kept_unit_id: str,
    kept_entity_id: str,
) -> None:
    """Test that devices are removed when units disappear from the account."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_unit_id), mock_config_entry.entry_id
    )

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, removed_units_key: []} for building in fixture["buildings"]
            ],
        }
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_unit_id), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, kept_unit_id), mock_config_entry.entry_id
    )
    assert hass.states.get(removed_entity_id) is None
    assert (state := hass.states.get(kept_entity_id))
    assert state.state != STATE_UNAVAILABLE


async def test_empty_context_keeps_devices(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a context without any units keeps the devices but marks them unavailable."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    await setup_integration(hass, mock_config_entry)

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {**fixture, "buildings": [], "guestBuildings": []}
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "ata-unit-uuid-1"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "atw-unit-uuid-1"), mock_config_entry.entry_id
    )
    assert hass.states.get("climate.living_room_ac").state == STATE_UNAVAILABLE
    assert hass.states.get("climate.heat_pump_zone_1").state == STATE_UNAVAILABLE

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(fixture)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("climate.living_room_ac").state != STATE_UNAVAILABLE
    assert hass.states.get("climate.heat_pump_zone_1").state != STATE_UNAVAILABLE


async def test_new_atw_unit_callback(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new ATW units discovered on coordinator refresh create climate entities."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToWaterUnits": []} for building in fixture["buildings"]
            ],
        }
    )
    await setup_integration(hass, mock_config_entry)
    atw_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "heat_pump" in entity.entity_id
    ]
    assert not atw_entities

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(fixture)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    atw_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "heat_pump" in entity.entity_id
    ]
    assert atw_entities


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), id="auth"),
        pytest.param(MelCloudHomeConnectionError("cannot connect"), id="connection"),
        pytest.param(MelCloudHomeTimeoutError("timeout"), id="timeout"),
        pytest.param(MelCloudHomeNotFoundError("not found"), id="api_error"),
    ],
)
async def test_energy_update_cycle_fails(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that a failing energy fetch clears the value without unloading the entry."""
    await setup_integration(hass, mock_config_entry)
    telemetry_coordinator = mock_config_entry.runtime_data.telemetry_coordinator

    assert telemetry_coordinator.data.energy["ata-unit-uuid-1"] is not None
    assert telemetry_coordinator.data.energy["atw-unit-uuid-1"] is not None

    mock_melcloud_client.get_energy_telemetry.side_effect = exception
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert telemetry_coordinator.data.energy["ata-unit-uuid-1"] is None
    assert telemetry_coordinator.data.energy["atw-unit-uuid-1"] is None

    # Demonstrate a recovery
    mock_melcloud_client.get_energy_telemetry.side_effect = None
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert telemetry_coordinator.data.energy["ata-unit-uuid-1"] is not None
    assert telemetry_coordinator.data.energy["atw-unit-uuid-1"] is not None


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), id="auth"),
        pytest.param(MelCloudHomeConnectionError("cannot connect"), id="connection"),
        pytest.param(MelCloudHomeTimeoutError("timeout"), id="timeout"),
        pytest.param(MelCloudHomeNotFoundError("not found"), id="api_error"),
    ],
)
async def test_energy_telemetry_fetch_failure(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that a failing energy telemetry fetch doesn't affect anything else."""
    await setup_integration(hass, mock_config_entry)

    mock_melcloud_client.get_energy_telemetry.side_effect = exception
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        mock_config_entry.runtime_data.telemetry_coordinator.last_update_success is True
    )
    assert mock_config_entry.runtime_data.coordinator.last_update_success is True


async def test_telemetry_reuses_main_coordinator_context(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the telemetry coordinator uses the units of the main coordinator."""
    await setup_integration(hass, mock_config_entry)

    mock_melcloud_client.get_context.assert_called_once()
    assert mock_config_entry.runtime_data.telemetry_coordinator.data.energy == {
        "ata-unit-uuid-1": 450.5,
        "atw-unit-uuid-1": 450.5,
    }

    mock_melcloud_client.get_context.reset_mock()
    mock_melcloud_client.get_energy_telemetry.reset_mock()
    mock_melcloud_client.get_outdoor_temperature.reset_mock()
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_melcloud_client.get_context.assert_called_once()
    assert mock_melcloud_client.get_energy_telemetry.call_count == 2
    mock_melcloud_client.get_outdoor_temperature.assert_called_once()


async def test_telemetry_skipped_while_context_fetch_fails(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the telemetry coordinator fails without API calls while the main one fails."""
    await setup_integration(hass, mock_config_entry)

    mock_melcloud_client.get_context.side_effect = MelCloudHomeConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_melcloud_client.get_energy_telemetry.reset_mock()
    mock_melcloud_client.get_outdoor_temperature.reset_mock()
    freezer.tick(TELEMETRY_UPDATE_INTERVAL - UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        mock_config_entry.runtime_data.telemetry_coordinator.last_update_success
        is False
    )
    assert (state := hass.states.get("sensor.living_room_ac_energy_consumed_monthly"))
    assert state.state == STATE_UNAVAILABLE
    mock_melcloud_client.get_energy_telemetry.assert_not_called()
    mock_melcloud_client.get_outdoor_temperature.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), id="auth"),
        pytest.param(MelCloudHomeConnectionError("cannot connect"), id="connection"),
        pytest.param(MelCloudHomeTimeoutError("timeout"), id="timeout"),
        pytest.param(MelCloudHomeNotFoundError("not found"), id="api_error"),
    ],
)
async def test_outdoor_temperature_update_cycle_fails(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that a failing outdoor temperature fetch clears the value without unloading the entry."""
    await setup_integration(hass, mock_config_entry)
    telemetry_coordinator = mock_config_entry.runtime_data.telemetry_coordinator

    assert telemetry_coordinator.data.outdoor_temperature["ata-unit-uuid-1"] is not None

    mock_melcloud_client.get_outdoor_temperature.side_effect = exception
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert telemetry_coordinator.data.outdoor_temperature["ata-unit-uuid-1"] is None

    mock_melcloud_client.get_outdoor_temperature.side_effect = None
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert telemetry_coordinator.data.outdoor_temperature["ata-unit-uuid-1"] is not None


@pytest.mark.parametrize(
    ("method", "name"),
    [
        pytest.param("get_energy_telemetry", "Energy telemetry", id="energy"),
        pytest.param(
            "get_outdoor_temperature", "Outdoor temperature", id="outdoor_temperature"
        ),
    ],
)
async def test_telemetry_unavailable_logged_once(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    method: str,
    name: str,
) -> None:
    """Test a failing telemetry fetch is logged once, and once when it recovers."""
    await setup_integration(hass, mock_config_entry)
    unavailable = f"{name} for ata-unit-uuid-1 is unavailable"
    available = f"{name} for ata-unit-uuid-1 is available again"

    getattr(mock_melcloud_client, method).side_effect = MelCloudHomeConnectionError
    for _ in range(2):
        freezer.tick(TELEMETRY_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count(unavailable) == 1
    assert available not in caplog.text

    getattr(mock_melcloud_client, method).side_effect = None
    for _ in range(2):
        freezer.tick(TELEMETRY_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count(unavailable) == 1
    assert caplog.text.count(available) == 1


@pytest.mark.usefixtures("mock_melcloud_client")
@pytest.mark.parametrize(
    ("platform", "old_unique_id", "new_unique_id"),
    [
        pytest.param(
            Platform.CLIMATE, "ata-unit-uuid-1", "ata-unit-uuid-1_ata_unit", id="ata"
        ),
        pytest.param(
            Platform.CLIMATE,
            "atw-unit-uuid-1_zone_1",
            "atw-unit-uuid-1_zone_1",
            id="atw_zone",
        ),
        pytest.param(
            Platform.SENSOR,
            "ata-unit-uuid-1_room_temperature",
            "ata-unit-uuid-1_room_temperature",
            id="other_platform",
        ),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: Platform,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test the unique ID migration to the entity description key."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        platform, DOMAIN, old_unique_id, config_entry=entry
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    entity_entry = entity_registry.async_get(entity.entity_id)
    assert entity_entry
    assert entity_entry.unique_id == new_unique_id
    # The platform must pick up the migrated entry instead of creating a new one
    assert hass.states.get(entity.entity_id)


async def test_migrate_future_version(hass: HomeAssistant) -> None:
    """Test a config entry from a newer version isn't migrated."""
    entry = MockConfigEntry(domain=DOMAIN, version=2)

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
