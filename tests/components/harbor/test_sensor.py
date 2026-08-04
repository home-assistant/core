"""Test the Harbor sensors."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import (
    HEARTBEAT_PAYLOAD,
    HEARTBEAT_TOPIC,
    LIVEKIT_PAYLOAD,
    LIVEKIT_TOPIC,
    emit_message,
)

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Harbor sensors report their values."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)
    await emit_message(mock_mqtt_client, LIVEKIT_TOPIC, LIVEKIT_PAYLOAD)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_missing_values_are_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test sensors without a value in the payload report unknown."""
    await setup_integration(hass, mock_config_entry)

    # Only the heartbeat arrives; sensors fed by the LiveKit message stay unknown.
    await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.harbor_camera_1234567890_temperature").state == "37.0"
    )
    assert (
        hass.states.get("sensor.harbor_camera_1234567890_bitrate").state
        == STATE_UNKNOWN
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unexpected_enum_value_stays_valid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test a stream quality outside the declared options surfaces as unknown.

    The library maps unrecognized enum values onto its own "unknown" member;
    the sensor treats that as no value rather than exposing "unknown" as a
    literal enum option.
    """
    await setup_integration(hass, mock_config_entry)
    entity_id = "sensor.harbor_camera_1234567890_stream_quality"

    await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)
    await emit_message(mock_mqtt_client, LIVEKIT_TOPIC, LIVEKIT_PAYLOAD)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "good"

    # The camera reports a stream quality outside the known set.
    await emit_message(
        mock_mqtt_client,
        LIVEKIT_TOPIC,
        {**LIVEKIT_PAYLOAD, "stream_quality": "DEGRADED"},
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
