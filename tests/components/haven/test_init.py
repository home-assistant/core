"""Test setup for the HAVEN IAQ integration."""

from unittest.mock import AsyncMock, patch

from haveniaq import (
    DeviceInfo,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
    SensorData,
)
import pytest

from homeassistant.components.haven.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import TEST_HOST, TEST_INFO, TEST_SENSORS, TEST_UNSUPPORTED_CONTROLLER_INFO

from tests.common import MockConfigEntry


async def test_setup_unload_ram_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading an air-quality entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.haven.HavenClient") as client_class:
        client = AsyncMock()
        client.get_info.return_value = DeviceInfo.from_dict(TEST_INFO)
        client.get_sensors.return_value = SensorData.from_dict(TEST_SENSORS)
        client_class.return_value = client

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        client.get_sensors.assert_awaited_once()
        client.get_status.assert_not_awaited()
        client.get_controller.assert_not_awaited()
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "error",
    [
        HavenUnsupportedApiVersionError("Unsupported API version"),
        HavenUnsupportedProductError("Unsupported product"),
    ],
)
async def test_setup_unsupported_device(hass: HomeAssistant, error: Exception) -> None:
    """Test unsupported devices fail setup without retrying."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.haven.HavenClient") as client_class:
        client = AsyncMock()
        client.get_info.side_effect = error
        client_class.return_value = client

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_device_without_air_quality(hass: HomeAssistant) -> None:
    """Test a device without air-quality capability fails setup permanently."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.haven.HavenClient") as client_class:
        client = AsyncMock()
        client.get_info.return_value = DeviceInfo.from_dict(
            TEST_UNSUPPORTED_CONTROLLER_INFO
        )
        client_class.return_value = client

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
