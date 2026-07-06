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
from homeassistant.components.melcloud_home.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
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

    assert device_registry.async_get_device(identifiers={(DOMAIN, "ata-unit-uuid-1")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "atw-unit-uuid-1")})

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
        device_registry.async_get_device(identifiers={(DOMAIN, "ata-unit-uuid-1")})
        is None
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "atw-unit-uuid-1")})
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
