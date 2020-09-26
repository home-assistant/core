"""Tests for Water heater."""
from homeassistant.components import water_heater


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomWaterHeater(water_heater.WaterHeaterDevice):
        pass

    CustomWaterHeater()
    assert "WaterHeaterDevice is deprecated, modify CustomWaterHeater" in caplog.text
