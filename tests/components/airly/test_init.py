"""Test init of Airly integration."""

from typing import Any
from unittest.mock import MagicMock

from airly.measurements import Measurement
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.airly.const import DOMAIN
from homeassistant.components.airly.coordinator import set_update_interval
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_airly_client")
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.home_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4.37"


async def test_config_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Test for setup failure if connection to Airly is missing."""
    mock_airly_client.create_measurements_session_point.return_value.update.side_effect = ConnectionError()

    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_airly_client")
async def test_config_without_unique_id(hass: HomeAssistant) -> None:
    """Test for setup entry without unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 12.3,
            CONF_LONGITUDE: 45.6,
        },
    )

    await init_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "12.3-45.6"


async def test_config_with_turned_off_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    mock_airly_no_station_measurements: Measurement,
) -> None:
    """Test for setup entry for a turned off measuring station."""
    mock_airly_client.create_measurements_session_point.return_value.current = (
        mock_airly_no_station_measurements
    )

    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_interval(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test correct update interval when the number of configured instances changes."""
    REMAINING_REQUESTS = 15
    mock_airly_client.requests_remaining = REMAINING_REQUESTS

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="12.3-45.6",
        data={
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 12.3,
            CONF_LONGITUDE: 45.6,
        },
    )

    await init_integration(hass, entry)
    instances = 1

    create_measurements = mock_airly_client.create_measurements_session_point
    assert create_measurements.call_count == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    update_interval = set_update_interval(instances, REMAINING_REQUESTS)
    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # call_count should increase by one because we have one instance configured
    assert create_measurements.call_count == 2

    # Now we add the second Airly instance
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Work",
        unique_id="66.66-111.11",
        data={
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 66.66,
            CONF_LONGITUDE: 111.11,
        },
    )

    await init_integration(hass, entry)
    instances = 2

    assert create_measurements.call_count == 3
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert entry.state is ConfigEntryState.LOADED

    update_interval = set_update_interval(instances, REMAINING_REQUESTS)
    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # call_count should increase by two because we have two instances configured
    assert create_measurements.call_count == 5


@pytest.mark.usefixtures("mock_airly_client")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize("old_identifier", [(DOMAIN, 123, 456), (DOMAIN, "123", "456")])
@pytest.mark.usefixtures("mock_airly_client")
async def test_migrate_device_entry(
    hass: HomeAssistant,
    old_identifier: tuple[str, Any, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device_info identifiers migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123-456",
        data={
            CONF_API_KEY: "foo",
            CONF_LATITUDE: 123,
            CONF_LONGITUDE: 456,
        },
    )
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={old_identifier}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "123-456")}
    )
    assert device_entry.id == migrated_device_entry.id


async def test_remove_air_quality_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_airly_client: MagicMock,
) -> None:
    """Test remove air_quality entities from registry."""
    entity_registry.async_get_or_create(
        AIR_QUALITY_DOMAIN,
        DOMAIN,
        "12.3-45.6",
        suggested_object_id="home",
        disabled_by=None,
    )

    await init_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("air_quality.home")
    assert entry is None
