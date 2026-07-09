"""Test the Harbor integration setup and coordinator."""

from unittest.mock import AsyncMock, patch

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

# The device is registered with its default name before any message sets a
# display name, so the entity id derives from that default name.
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

    with patch("homeassistant.components.harbor.coordinator.CONNECT_TIMEOUT", 0):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_mqtt_client.return_value.stop.called


async def test_availability_follows_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: AsyncMock,
) -> None:
    """Test entity availability tracks the MQTT connection and device data."""
    await setup_integration(hass, mock_config_entry)

    # Connected after setup but no device data yet: unavailable.
    assert hass.states.get(_SENSOR).state == STATE_UNAVAILABLE

    # Device data arrives: entities become available.
    await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)
    await hass.async_block_till_done()
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
) -> None:
    """Test the device entry adopts the name and firmware from a heartbeat."""
    await setup_integration(hass, mock_config_entry)

    await emit_message(mock_mqtt_client, HEARTBEAT_TOPIC, HEARTBEAT_PAYLOAD)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.name == "Nursery"
    assert device.sw_version == "1.2.3"
