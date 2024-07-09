"""Tests for the MadVR sensor entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .conftest import get_update_callback

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the sensor entities."""
    with patch("homeassistant.components.madvr.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "payload", "expected_state", "expected_attributes"),
    [
        (
            "sensor.madvr_envy_gpu_temperature",
            {"temp_gpu": 45.5},
            "45.5",
            {
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        ),
        (
            "sensor.madvr_envy_hdmi_temperature",
            {"temp_hdmi": 40.0},
            "40.0",
            {
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        ),
        (
            "sensor.madvr_envy_cpu_temperature",
            {"temp_cpu": 50.2},
            "50.2",
            {
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        ),
        (
            "sensor.madvr_envy_mainboard_temperature",
            {"temp_mainboard": 35.8},
            "35.8",
            {
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        ),
        (
            "sensor.madvr_envy_incoming_resolution",
            {"incoming_res": "3840x2160"},
            "3840x2160",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_frame_rate",
            {"incoming_frame_rate": "60Hz"},
            "60Hz",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_signal_type",
            {"outgoing_signal_type": "2D"},
            "2D",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_signal_type",
            {"incoming_signal_type": "3D"},
            "3D",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_color_space",
            {"incoming_color_space": "BT.2020"},
            "BT.2020",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_bit_depth",
            {"incoming_bit_depth": "10-bit"},
            "10-bit",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_colorimetry",
            {"incoming_colorimetry": "BT.2020"},
            "BT.2020",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_black_levels",
            {"incoming_black_levels": "Full"},
            "Full",
            {},
        ),
        (
            "sensor.madvr_envy_incoming_aspect_ratio",
            {"incoming_aspect_ratio": "16:9"},
            "16:9",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_resolution",
            {"outgoing_res": "3840x2160"},
            "3840x2160",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_frame_rate",
            {"outgoing_frame_rate": "60Hz"},
            "60Hz",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_color_space",
            {"outgoing_color_space": "BT.2020"},
            "BT.2020",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_bit_depth",
            {"outgoing_bit_depth": "10-bit"},
            "10-bit",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_colorimetry",
            {"outgoing_colorimetry": "BT.2020"},
            "BT.2020",
            {},
        ),
        (
            "sensor.madvr_envy_outgoing_black_levels",
            {"outgoing_black_levels": "Full"},
            "Full",
            {},
        ),
        (
            "sensor.madvr_envy_aspect_ratio_resolution",
            {"aspect_res": "3840x2160"},
            "3840x2160",
            {},
        ),
        (
            "sensor.madvr_envy_aspect_ratio_decimal",
            {"aspect_dec": "1.78"},
            "1.78",
            {},
        ),
        (
            "sensor.madvr_envy_aspect_ratio_integer",
            {"aspect_int": "16:9"},
            "16:9",
            {},
        ),
        (
            "sensor.madvr_envy_aspect_ratio_name",
            {"aspect_name": "16:9"},
            "16:9",
            {},
        ),
        (
            "sensor.madvr_envy_masking_resolution",
            {"masking_res": "3840x2160"},
            "3840x2160",
            {},
        ),
        (
            "sensor.madvr_envy_masking_decimal",
            {"masking_dec": "1.78"},
            "1.78",
            {},
        ),
        (
            "sensor.madvr_envy_masking_integer",
            {"masking_int": "16:9"},
            "16:9",
            {},
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    payload: dict,
    expected_state: str,
    expected_attributes: dict,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)
    update_callback = get_update_callback(mock_madvr_client)

    # Test sensor state and attributes
    update_callback(payload)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == expected_state
    for attr, value in expected_attributes.items():
        assert state.attributes.get(attr) == value


async def test_temperature_sensor_invalid_value(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test temperature sensor with invalid value."""
    await setup_integration(hass, mock_config_entry)
    update_callback = get_update_callback(mock_madvr_client)

    # Test invalid temperature value
    update_callback({"temp_gpu": -1})  # Invalid temperature
    await hass.async_block_till_done()

    state = hass.states.get("sensor.madvr_envy_gpu_temperature")
    assert state.state == "unknown"


async def test_sensor_availability(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor availability."""
    await setup_integration(hass, mock_config_entry)
    update_callback = get_update_callback(mock_madvr_client)

    # Test sensor becomes unknown
    update_callback({"incoming_res": None})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.madvr_envy_incoming_resolution")
    assert state.state == "unknown"

    # Test sensor becomes available again
    update_callback({"incoming_res": "1920x1080"})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.madvr_envy_incoming_resolution")
    assert state.state == "1920x1080"
