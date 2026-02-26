"""Tests for MQTT coordinator lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.victron_remote_monitoring.coordinator import (
    VictronRemoteMonitoringDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from .conftest import FakeMQTTClient


async def test_coordinator_mqtt_start_stop(
    hass: HomeAssistant,
    mock_config_entry,
    mock_mqtt_client: FakeMQTTClient,
) -> None:
    """Verify start/stop behavior."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)

    await coordinator.start_mqtt()

    assert coordinator.mqtt_client is mock_mqtt_client

    await coordinator.stop_mqtt()

    assert coordinator.mqtt_client is None


async def test_coordinator_start_mqtt_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_mqtt_client: FakeMQTTClient,
) -> None:
    """Verify start_mqtt failure handling."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)
    mock_mqtt_client.connect = AsyncMock(
        side_effect=RuntimeError("Something went wrong")
    )

    with pytest.raises(RuntimeError):
        await coordinator.start_mqtt()

    assert coordinator.mqtt_client is None


async def test_coordinator_start_mqtt_idempotent(
    hass: HomeAssistant,
    mock_config_entry,
    mock_mqtt_client: FakeMQTTClient,
) -> None:
    """Verify start_mqtt is idempotent."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)

    await coordinator.start_mqtt()
    await coordinator.start_mqtt()

    assert coordinator.mqtt_client is mock_mqtt_client


async def test_coordinator_stop_mqtt_failure(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Verify stop_mqtt error propagation and cleanup."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)

    class _FailingClient:
        async def disconnect(self) -> None:
            raise RuntimeError("Something went wrong during disconnect")

    coordinator.mqtt_client = _FailingClient()

    with pytest.raises(RuntimeError):
        await coordinator.stop_mqtt()

    assert coordinator.mqtt_client is None


async def test_coordinator_stop_mqtt_idempotent(
    hass: HomeAssistant,
    mock_config_entry,
    mock_mqtt_client: FakeMQTTClient,
) -> None:
    """Verify stop_mqtt is idempotent."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)

    await coordinator.start_mqtt()
    await coordinator.stop_mqtt()
    await coordinator.stop_mqtt()

    assert coordinator.mqtt_client is None


async def test_coordinator_stop_mqtt_no_client(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Verify stop_mqtt handles missing client."""
    coordinator = VictronRemoteMonitoringDataUpdateCoordinator(hass, mock_config_entry)

    await coordinator.stop_mqtt()

    assert coordinator.mqtt_client is None
