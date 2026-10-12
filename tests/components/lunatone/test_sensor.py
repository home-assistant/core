"""Tests for the lights provided by the Lunatone integration."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client.models import LineStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone sensor setup."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.SENSOR)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


@pytest.mark.parametrize(
    ("sensor_id", "entity_id", "expected_state"),
    [
        (1, "sensor.test_temperature", "22"),
        (2, "sensor.test_air_humidity", "55"),
        (3, "sensor.dali_line_0_a02_temperature", "20"),
    ],
    ids=["temperature", "air_humidity", "dali_temperature"],
)
async def test_sensor_value_update(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    sensor_id: int,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the Lunatone sensor value update."""
    await setup_integration(hass, mock_config_entry)

    async def fake_update() -> None:
        for sensor_data in mock_lunatone_sensors.data.sensors:
            if sensor_data.id == sensor_id:
                sensor_data.value = int(expected_state)

    mock_lunatone_sensors.async_update.side_effect = fake_update

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == "unknown"

    freezer.tick(timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == expected_state


async def test_dali_line_status_value_update(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Lunatone sensor value update."""
    line_id = 0
    entity_id = f"sensor.dali_line_{line_id}_status"

    line_statuses = iter((LineStatus.NO_POWER, LineStatus.OK))

    async def fake_update() -> None:
        info_data = deepcopy(mock_lunatone_info.data)
        info_data.lines[str(line_id)].line_status = next(line_statuses)
        mock_lunatone_info.data = info_data

    mock_lunatone_info.async_update.side_effect = fake_update

    await setup_integration(hass, mock_config_entry)

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == "no_power"

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == "ok"
