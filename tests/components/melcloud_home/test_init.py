"""Test the MELCloud Home integration init behavior."""

from unittest.mock import AsyncMock

from aiomelcloudhome import UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.components.melcloud_home.coordinator import (
    ENERGY_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

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
    ("exception", "setup_state"),
    [
        (MelCloudHomeAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (MelCloudHomeConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (MelCloudHomeTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_entry_setup_retry_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    exception: Exception,
    setup_state: ConfigEntryState,
) -> None:
    """Test setup retries when initial coordinator refresh fails."""
    mock_melcloud_client.get_context.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is setup_state


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


async def test_stale_devices_removed(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that devices are removed when units disappear from the account."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "ata-unit-uuid-1"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "atw-unit-uuid-1"), mock_config_entry.entry_id
    )

    # Poof, now they're gone
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToAirUnits": [], "airToWaterUnits": []}
                for building in fixture["buildings"]
            ],
        }
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "ata-unit-uuid-1"), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "atw-unit-uuid-1"), mock_config_entry.entry_id
        )
        is None
    )


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
    energy_coordinator = mock_config_entry.runtime_data.energy_coordinator

    assert energy_coordinator.data["ata-unit-uuid-1"] is not None
    assert energy_coordinator.data["atw-unit-uuid-1"] is not None

    mock_melcloud_client.get_energy_telemetry.side_effect = exception
    freezer.tick(ENERGY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert energy_coordinator.data["ata-unit-uuid-1"] is None
    assert energy_coordinator.data["atw-unit-uuid-1"] is None

    # Demonstrate a recovery
    mock_melcloud_client.get_energy_telemetry.side_effect = None
    freezer.tick(ENERGY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert energy_coordinator.data["ata-unit-uuid-1"] is not None
    assert energy_coordinator.data["atw-unit-uuid-1"] is not None


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), id="auth"),
        pytest.param(MelCloudHomeConnectionError("cannot connect"), id="connection"),
        pytest.param(MelCloudHomeTimeoutError("timeout"), id="timeout"),
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
    freezer.tick(ENERGY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.energy_coordinator.last_update_success is True
    assert mock_config_entry.runtime_data.coordinator.last_update_success is True


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(MelCloudHomeAuthenticationError("bad creds"), id="auth"),
        pytest.param(MelCloudHomeConnectionError("cannot connect"), id="connection"),
        pytest.param(MelCloudHomeTimeoutError("timeout"), id="timeout"),
    ],
)
async def test_energy_coordinator_context_fetch_failure(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that a failing energy coordinator refresh doesn't affect the main coordinator."""
    await setup_integration(hass, mock_config_entry)

    # Split the margin so the main coordinator's rescheduled refresh doesn't land
    # exactly on the energy coordinator's, which would make both fail below.
    freezer.tick(ENERGY_UPDATE_INTERVAL - UPDATE_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_melcloud_client.get_context.side_effect = exception
    freezer.tick(UPDATE_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        energy_sensor := hass.states.get(
            "sensor.living_room_ac_energy_consumed_monthly"
        )
    )
    assert energy_sensor.state == STATE_UNAVAILABLE

    assert (
        room_temperature_sensor := hass.states.get(
            "sensor.living_room_ac_room_temperature"
        )
    )
    assert room_temperature_sensor.state != STATE_UNAVAILABLE
