"""Tests for helpers functions in the Saunum integration."""

from __future__ import annotations

from homeassistant.components.saunum import helpers
from homeassistant.components.saunum.const import (
    CONF_SAUNA_TYPE_1_NAME,
    CONF_SAUNA_TYPE_3_NAME,
    DEFAULT_SAUNA_TYPE_1_NAME,
    DEFAULT_SAUNA_TYPE_2_NAME,
    DEFAULT_SAUNA_TYPE_3_NAME,
)
from homeassistant.const import UnitOfTemperature

from tests.common import MockConfigEntry


def test_convert_temperature_none() -> None:
    """Test convert_temperature returns None when value is None."""
    assert (
        helpers.convert_temperature(
            None, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
        is None
    )


def test_convert_temperature_same_unit() -> None:
    """Test convert_temperature returns original value when units match."""
    assert (
        helpers.convert_temperature(
            80.0, UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS
        )
        == 80.0
    )


def test_convert_temperature_different_units() -> None:
    """Test convert_temperature performs conversion between units."""
    # 80C should be 176F
    assert (
        helpers.convert_temperature(
            80.0, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
        == 176.0
    )


def test_get_temperature_range_for_unit_fahrenheit() -> None:
    """Test Fahrenheit temperature range values."""
    minimum, maximum, default = helpers.get_temperature_range_for_unit(
        UnitOfTemperature.FAHRENHEIT
    )
    assert minimum == 104  # 40C
    assert maximum == 212  # 100C
    assert default == 176  # 80C


def test_get_custom_sauna_type_names_all_defaults() -> None:
    """Test custom sauna type names fallback to defaults when options missing."""
    entry = MockConfigEntry(domain="saunum", data={}, options={})
    names = helpers.get_custom_sauna_type_names(entry)
    assert names[0] == DEFAULT_SAUNA_TYPE_1_NAME
    assert names[1] == DEFAULT_SAUNA_TYPE_2_NAME
    assert names[2] == DEFAULT_SAUNA_TYPE_3_NAME


def test_get_custom_sauna_type_names_partial_overrides() -> None:
    """Test custom sauna type names with partial overrides in options."""
    entry = MockConfigEntry(
        domain="saunum",
        data={},
        options={
            CONF_SAUNA_TYPE_1_NAME: "Calm",
            CONF_SAUNA_TYPE_3_NAME: "Intense",
        },
    )
    names = helpers.get_custom_sauna_type_names(entry)
    assert names[0] == "Calm"
    # Type 2 falls back
    assert names[1] == DEFAULT_SAUNA_TYPE_2_NAME
    assert names[2] == "Intense"


class DummyUnits:
    """Dummy units container mimicking Home Assistant config.units."""

    def __init__(self, temperature_unit: str) -> None:
        """Initialize dummy units with a temperature unit string."""
        self.temperature_unit = temperature_unit


class DummyHass:
    """Minimal hass-like object for temperature unit retrieval."""

    def __init__(self, unit: str) -> None:
        """Initialize dummy hass object with provided temperature unit."""
        self.config = type("Config", (), {"units": DummyUnits(unit)})()


def test_get_temperature_unit() -> None:
    """Test get_temperature_unit returns configured unit string."""
    hass = DummyHass(UnitOfTemperature.CELSIUS)
    assert helpers.get_temperature_unit(hass) == UnitOfTemperature.CELSIUS


def test_get_temperature_range_for_unit_celsius() -> None:
    """Test Celsius temperature range values (else branch)."""
    minimum, maximum, default = helpers.get_temperature_range_for_unit(
        UnitOfTemperature.CELSIUS
    )
    assert minimum == 40
    assert maximum == 100
    assert default == 80


def test_convert_temperature_reverse_units() -> None:
    """Test convert_temperature performs reverse conversion (F->C)."""
    assert (
        helpers.convert_temperature(
            176.0, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
        )
        == 80.0
    )
