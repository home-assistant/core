"""Tests for the Electra Smart climate platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.electrasmart.climate import ElectraClimateEntity


@pytest.fixture
def mock_device():
    """Create a mock Electra AC device."""
    device = MagicMock()
    device.mac = "AA:BB:CC:DD:EE:FF"
    device.name = "Test AC"
    device.model = "Test Model"
    device.manufactor = "Electra"
    device.features = []
    return device


@pytest.fixture
def mock_api():
    """Create a mock Electra API."""
    return MagicMock()


@pytest.fixture
def climate_entity(mock_device, mock_api):
    """Create an ElectraClimateEntity for testing."""
    with patch.object(ElectraClimateEntity, "__init__", lambda self, *a, **kw: None):
        entity = ElectraClimateEntity.__new__(ElectraClimateEntity)
        entity._electra_ac_device = mock_device
        return entity


def test_sensor_temperature_scaled_down(climate_entity):
    """Test that raw temperatures above 100 are right-shifted by 8 bits."""
    climate_entity._electra_ac_device.get_sensor_temperature.return_value = 5632
    climate_entity._electra_ac_device.get_fan_speed.return_value = "AUTO"
    climate_entity._electra_ac_device.get_temperature.return_value = 24
    climate_entity._electra_ac_device.is_on.return_value = True
    climate_entity._electra_ac_device.get_mode.return_value = "COOL"
    climate_entity._electra_ac_device.is_horizontal_swing.return_value = False
    climate_entity._electra_ac_device.is_vertical_swing.return_value = False
    climate_entity._electra_ac_device.get_shabat_mode.return_value = False

    with patch(
        "homeassistant.components.electrasmart.climate.FAN_ELECTRA_TO_HASS",
        {"AUTO": "auto"},
    ), patch(
        "homeassistant.components.electrasmart.climate.HVAC_MODE_ELECTRA_TO_HASS",
        {"COOL": "cool"},
    ):
        climate_entity._update_device_attrs()

    assert climate_entity._attr_current_temperature == 22


def test_sensor_temperature_5888_becomes_23(climate_entity):
    """Test that raw value 5888 becomes 23°C."""
    climate_entity._electra_ac_device.get_sensor_temperature.return_value = 5888
    climate_entity._electra_ac_device.get_fan_speed.return_value = "AUTO"
    climate_entity._electra_ac_device.get_temperature.return_value = 24
    climate_entity._electra_ac_device.is_on.return_value = True
    climate_entity._electra_ac_device.get_mode.return_value = "COOL"
    climate_entity._electra_ac_device.is_horizontal_swing.return_value = False
    climate_entity._electra_ac_device.is_vertical_swing.return_value = False
    climate_entity._electra_ac_device.get_shabat_mode.return_value = False

    with patch(
        "homeassistant.components.electrasmart.climate.FAN_ELECTRA_TO_HASS",
        {"AUTO": "auto"},
    ), patch(
        "homeassistant.components.electrasmart.climate.HVAC_MODE_ELECTRA_TO_HASS",
        {"COOL": "cool"},
    ):
        climate_entity._update_device_attrs()

    assert climate_entity._attr_current_temperature == 23


def test_sensor_temperature_normal_passthrough(climate_entity):
    """Test that normal temperatures <= 100 pass through unchanged."""
    climate_entity._electra_ac_device.get_sensor_temperature.return_value = 24
    climate_entity._electra_ac_device.get_fan_speed.return_value = "AUTO"
    climate_entity._electra_ac_device.get_temperature.return_value = 24
    climate_entity._electra_ac_device.is_on.return_value = True
    climate_entity._electra_ac_device.get_mode.return_value = "COOL"
    climate_entity._electra_ac_device.is_horizontal_swing.return_value = False
    climate_entity._electra_ac_device.is_vertical_swing.return_value = False
    climate_entity._electra_ac_device.get_shabat_mode.return_value = False

    with patch(
        "homeassistant.components.electrasmart.climate.FAN_ELECTRA_TO_HASS",
        {"AUTO": "auto"},
    ), patch(
        "homeassistant.components.electrasmart.climate.HVAC_MODE_ELECTRA_TO_HASS",
        {"COOL": "cool"},
    ):
        climate_entity._update_device_attrs()

    assert climate_entity._attr_current_temperature == 24


def test_sensor_temperature_none_when_ac_off(climate_entity):
    """Test that None temperature (AC off) stays None."""
    climate_entity._electra_ac_device.get_sensor_temperature.return_value = None
    climate_entity._electra_ac_device.get_fan_speed.return_value = "AUTO"
    climate_entity._electra_ac_device.get_temperature.return_value = 24
    climate_entity._electra_ac_device.is_on.return_value = False
    climate_entity._electra_ac_device.is_horizontal_swing.return_value = False
    climate_entity._electra_ac_device.is_vertical_swing.return_value = False
    climate_entity._electra_ac_device.get_shabat_mode.return_value = False

    with patch(
        "homeassistant.components.electrasmart.climate.FAN_ELECTRA_TO_HASS",
        {"AUTO": "auto"},
    ):
        climate_entity._update_device_attrs()

    assert climate_entity._attr_current_temperature is None
