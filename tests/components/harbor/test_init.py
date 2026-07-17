"""Test the Harbor integration setup and coordinator."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.harbor.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import (
    HEARTBEAT_PAYLOAD,
    HEARTBEAT_TOPIC,
    SERIAL,
    emit_message,
    set_connected,
)

from tests.common import MockConfigEntry

# The default test fixture reports no device data on connect, so the device
# keeps its placeholder name and the entity id derives from that.
_SENSOR = "sensor.harbor_camera_1234567890_temperature"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test a config entry loads, starts the client, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_mqtt_client.return_value.start.called

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_mqtt_client.return_value.stop.called


async def test_setup_uses_instance_scoped_mqtt_client_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test setup uses an MQTT client id unique to this HA instance."""
    await setup_integration(hass, mock_config_entry)

    client_id = mock_mqtt_client.call_args.kwargs["client_id"]

    assert client_id.startswith(f"{DOMAIN}-")
    assert client_id.endswith(f"-{SERIAL}")
    assert client_id != f"{DOMAIN}-{SERIAL}"


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test setup is retried when the camera never connects."""
    # Start the client without ever reporting a successful connection.
    mock_mqtt_client.return_value.start.side_effect = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_mqtt_client.return_value.stop.called


async def test_setup_retry_when_no_data_arrives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test setup is retried when the camera connects but never sends data."""

    async def _start() -> None:
        await set_connected(mock_mqtt_client, True)

    mock_mqtt_client.return_value.start.side_effect = _start

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_mqtt_client.return_value.stop.called


async def test_availability_follows_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test entity availability tracks the MQTT connection."""
    await setup_integration(hass, mock_config_entry)

    # Setup waits for the first device message, so entities start available.
    assert hass.states.get(_SENSOR).state != STATE_UNAVAILABLE

    # A repeated connected signal is a no-op and keeps entities available.
    await set_connected(mock_mqtt_client, True)
    await hass.async_block_till_done()
    assert hass.states.get(_SENSOR).state != STATE_UNAVAILABLE

    # Losing the connection flips entities back to unavailable.
    await set_connected(mock_mqtt_client, False)
    await hass.async_block_till_done()
    assert hass.states.get(_SENSOR).state == STATE_UNAVAILABLE

    # Reconnecting restores availability without needing fresh device data.
    await set_connected(mock_mqtt_client, True)
    await hass.async_block_till_done()
    assert hass.states.get(_SENSOR).state != STATE_UNAVAILABLE


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device adopts the name and firmware from the first message.

    Setup waits for that first message before registering entities, so the
    device is correct from the start instead of needing a later reload.
    """

    async def _start() -> None:
        await set_connected(mock_mqtt_client, True)
        await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)

    mock_mqtt_client.return_value.start.side_effect = _start

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device == snapshot
