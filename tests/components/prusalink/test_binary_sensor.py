"""Test Prusalink sensors."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def setup_binary_sensor_platform_only():
    """Only setup sensor platform."""
    with patch(
        "homeassistant.components.prusalink.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_no_job(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("binary_sensor.workshop_mock_title_mmu")
    assert state is not None
    assert state.state == STATE_OFF


async def test_status_connect_enabled_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """Connect binary sensor is enabled by default and reflects status_connect.ok."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("binary_sensor.workshop_mock_title_connectivity")
    assert state is not None
    assert state.state == STATE_ON


async def test_status_connect_not_created_when_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_idle: dict[str, Any],
) -> None:
    """Connect sensor is not created when status_connect is not in the response."""
    del mock_get_status_idle["printer"]["status_connect"]
    assert await async_setup_component(hass, "prusalink", {})

    assert hass.states.get("binary_sensor.workshop_mock_title_connectivity") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sd_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """SD card sensor reflects sd_ready from info endpoint."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("binary_sensor.workshop_mock_title_sd_card")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_farm_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """Farm mode sensor reflects farm_mode from info endpoint."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("binary_sensor.workshop_mock_title_farm_mode")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_farm_mode_not_created_when_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_info_api: dict[str, Any],
) -> None:
    """Farm mode sensor is not created when farm_mode field is absent from info."""
    del mock_info_api["farm_mode"]
    assert await async_setup_component(hass, "prusalink", {})

    assert hass.states.get("binary_sensor.workshop_mock_title_farm_mode") is None
