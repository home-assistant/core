"""Test the OKOK Scale init."""

import pytest

from homeassistant.components.okokscale.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    OKOK_20_ADDRESS,
    OKOK_20_SERVICE_INFO,
    OKOK_C0_ADDRESS,
    OKOK_C0_SERVICE_INFO,
    OKOK_F0_ADDRESS,
    OKOK_F0_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("mock_config_entry", "service_info"),
    [
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_ADDRESS),
            OKOK_F0_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_ADDRESS),
            OKOK_20_SERVICE_INFO,
        ),
        (
            MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_ADDRESS),
            OKOK_C0_SERVICE_INFO,
        ),
    ],
)
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service_info: BluetoothServiceInfo,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "mock_config_entry",
    [
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_ADDRESS),
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_20_ADDRESS),
        MockConfigEntry(domain=DOMAIN, unique_id=OKOK_C0_ADDRESS),
    ],
)
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test entity unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=OKOK_F0_ADDRESS,
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    weight_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=f"{OKOK_F0_ADDRESS}-weight",
        config_entry=config_entry,
    )
    battery_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=f"{OKOK_F0_ADDRESS}-battery",
        config_entry=config_entry,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 2

    entity_migrated = entity_registry.async_get(weight_entity.entity_id)
    assert entity_migrated.unique_id == f"{OKOK_F0_ADDRESS}-mass"

    entity_migrated = entity_registry.async_get(battery_entity.entity_id)
    assert entity_migrated.unique_id == f"{OKOK_F0_ADDRESS}-battery_percent"
