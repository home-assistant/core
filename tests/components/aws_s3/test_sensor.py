"""Tests for the AWS S3 sensor platform."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from botocore.exceptions import BotoCoreError
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aws_s3.coordinator import SCAN_INTERVAL
from homeassistant.components.backup import AgentBackup
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test the creation and values of the AWS S3 sensors."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    assert (
        entity_entry := entity_registry.async_get(
            "sensor.bucket_test_total_size_of_backups"
        )
    )

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_sensor_availability(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the availability handling of the AWS S3 sensors."""
    await setup_integration(hass, mock_config_entry)

    mock_client.get_paginator.return_value.paginate.side_effect = BotoCoreError()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.bucket_test_total_size_of_backups"))
    assert state.state == STATE_UNAVAILABLE

    mock_client.get_paginator.return_value.paginate.side_effect = None
    mock_client.get_paginator.return_value.paginate.return_value.__aiter__.return_value = [
        {"Contents": []}
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.bucket_test_total_size_of_backups"))
    assert state.state != STATE_UNAVAILABLE


async def test_calculate_backups_size(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    test_backup: AgentBackup,
) -> None:
    """Test the total size of backups calculation."""
    mock_client.get_paginator.return_value.paginate.return_value.__aiter__.return_value = [
        {"Contents": []}
    ]
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.bucket_test_total_size_of_backups"))
    assert state.state == "0.0"

    # Add a backup
    metadata_content = json.dumps(test_backup.as_dict())
    mock_body = AsyncMock()
    mock_body.read.return_value = metadata_content.encode()
    mock_client.get_object.return_value = {"Body": mock_body}

    mock_client.get_paginator.return_value.paginate.return_value.__aiter__.return_value = [
        {
            "Contents": [
                {"Key": "backup.tar"},
                {"Key": "backup.metadata.json"},
            ]
        }
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.bucket_test_total_size_of_backups"))
    assert float(state.state) > 0
