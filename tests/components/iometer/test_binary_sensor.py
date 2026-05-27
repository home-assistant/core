"""Test the IOmeter binary sensors."""

import asyncio
import json
from unittest.mock import MagicMock

from iometer import Status
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, async_load_fixture, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensors."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_connection_status_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iometer_client: MagicMock,
    status_queue: asyncio.Queue[Status],
) -> None:
    """Test connection status sensor updates via SSE."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_bridge_connection_status"
        ).state
        == STATE_ON
    )

    status_data = json.loads(await async_load_fixture(hass, "status.json", DOMAIN))
    status_data["device"]["core"]["connectionStatus"] = "disconnected"
    status_queue.put_nowait(Status.from_json(json.dumps(status_data)))
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_bridge_connection_status"
        ).state
        == STATE_OFF
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_attachment_status_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iometer_client: MagicMock,
    status_queue: asyncio.Queue[Status],
) -> None:
    """Test attachment status sensor updates via SSE."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_ON
    )

    status_data = json.loads(await async_load_fixture(hass, "status.json", DOMAIN))
    status_data["device"]["core"]["attachmentStatus"] = "detached"
    status_queue.put_nowait(Status.from_json(json.dumps(status_data)))
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_OFF
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_attachment_status_sensors_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iometer_client: MagicMock,
    status_queue: asyncio.Queue[Status],
) -> None:
    """Test attachment status sensor shows unknown state via SSE."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_ON
    )

    status_data = json.loads(await async_load_fixture(hass, "status.json", DOMAIN))
    del status_data["device"]["core"]["attachmentStatus"]
    status_queue.put_nowait(Status.from_json(json.dumps(status_data)))
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.iometer_1isk0000000000_core_attachment_status"
        ).state
        == STATE_UNKNOWN
    )
