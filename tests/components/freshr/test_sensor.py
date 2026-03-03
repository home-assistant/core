"""Test the Fresh-r sensor platform."""

from unittest.mock import MagicMock

from aiohttp import ClientError
from pyfreshr.exceptions import ApiResponseError
from pyfreshr.models import DeviceReadings, DeviceSummary
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.freshr.const import DOMAIN
from homeassistant.components.freshr.coordinator import (
    DEVICES_SCAN_INTERVAL,
    READINGS_SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test sensors return unknown when all readings are None."""
    mock_freshr_client.fetch_device_current.return_value = DeviceReadings(
        t1=None, t2=None, co2=None, hum=None, flow=None, dp=None
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for key in ("t1", "t2", "co2", "hum", "flow", "dp"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DEVICE_ID}_{key}"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id).state == "unknown"


async def test_setup_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an empty device list sets up successfully with no entities."""
    mock_freshr_client.fetch_devices.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "error",
    [ApiResponseError("api error"), ClientError("network error")],
)
async def test_readings_connection_error_makes_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_freshr_client: MagicMock,
    error: Exception,
) -> None:
    """Test that connection errors during readings refresh mark entities unavailable."""
    mock_freshr_client.fetch_device_current.side_effect = error
    async_fire_time_changed(hass, dt_util.utcnow() + READINGS_SCAN_INTERVAL)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_t1")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_dynamic_device_addition(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that a device added to the account after setup is discovered dynamically."""
    second_device_id = "SN002"
    mock_freshr_client.fetch_devices.return_value = [
        DeviceSummary(id=DEVICE_ID),
        DeviceSummary(id=second_device_id),
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + DEVICES_SCAN_INTERVAL)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # wait for the readings coordinator task

    new_unique_ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.unique_id.startswith(second_device_id)
    }
    assert new_unique_ids == {
        f"{second_device_id}_t1",
        f"{second_device_id}_t2",
        f"{second_device_id}_co2",
        f"{second_device_id}_hum",
        f"{second_device_id}_flow",
        f"{second_device_id}_dp",
    }
