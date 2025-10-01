"""Tests for the Alexa Devices sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aioamazondevices.api import AmazonDeviceSensor
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1_SN

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotRetrieveData,
        CannotAuthenticate,
    ],
)
async def test_coordinator_data_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test coordinator data update exceptions."""

    entity_id = "sensor.echo_test_temperature"

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == "22.5"

    mock_amazon_devices_client.get_devices_data.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test offline device handling."""

    entity_id = "sensor.echo_test_temperature"

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("sensor", "api_value", "scale", "state_value", "unit"),
    [
        (
            "temperature",
            "86",
            "FAHRENHEIT",
            "30.0",  # State machine converts to °C
            "°C",  # State machine converts to °C
        ),
        ("temperature", "22.5", "CELSIUS", "22.5", "°C"),
        ("illuminance", "800", None, "800", "lx"),
    ],
)
async def test_unit_of_measurement(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sensor: str,
    api_value: Any,
    scale: str | None,
    state_value: Any,
    unit: str | None,
) -> None:
    """Test sensor unit of measurement handling."""

    entity_id = f"sensor.echo_test_{sensor}"

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].sensors = {
        sensor: AmazonDeviceSensor(
            name=sensor, value=api_value, error=False, scale=scale
        )
    }

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == state_value
    assert state.attributes["unit_of_measurement"] == unit


async def test_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor is unavailable."""

    entity_id = "sensor.echo_test_illuminance"

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].sensors = {
        "illuminance": AmazonDeviceSensor(
            name="illuminance", value="800", error=True, scale=None
        )
    }

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
