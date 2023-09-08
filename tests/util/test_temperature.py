"""Test Home Assistant temperature utility functions."""
import pytest

from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.temperature as temperature_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = UnitOfTemperature.CELSIUS


def test_raise_deprecation_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure that a warning is raised on use of convert."""
    assert (
        temperature_util.convert(
            2, UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS
        )
        == 2
    )
    assert "use unit_conversion.TemperatureConverter instead" in caplog.text


@pytest.mark.parametrize(
    ("function_name", "value", "expected"),
    [
        ("fahrenheit_to_celsius", 75.2, 24),
        ("kelvin_to_celsius", 297.65, 24.5),
        ("celsius_to_fahrenheit", 23, 73.4),
        ("celsius_to_kelvin", 23, 296.15),
    ],
)
def test_deprecated_functions(
    function_name: str, value: float, expected: float
) -> None:
    """Test that deprecated function still work."""
    convert = getattr(temperature_util, function_name)
    assert convert(value) == expected


def test_convert_same_unit() -> None:
    """Test conversion from any unit to same unit."""
    assert (
        temperature_util.convert(
            2, UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS
        )
        == 2
    )
    assert (
        temperature_util.convert(
            3, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT
        )
        == 3
    )
    assert (
        temperature_util.convert(4, UnitOfTemperature.KELVIN, UnitOfTemperature.KELVIN)
        == 4
    )


def test_convert_invalid_unit() -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        temperature_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        temperature_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value() -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        temperature_util.convert(
            "a", UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )


def test_convert_from_celsius() -> None:
    """Test conversion from C to other units."""
    celsius = 100
    assert temperature_util.convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
    ) == pytest.approx(212.0)
    assert temperature_util.convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.KELVIN
    ) == pytest.approx(373.15)
    # Interval
    assert temperature_util.convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT, True
    ) == pytest.approx(180.0)
    assert temperature_util.convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.KELVIN, True
    ) == pytest.approx(100)


def test_convert_from_fahrenheit() -> None:
    """Test conversion from F to other units."""
    fahrenheit = 100
    assert temperature_util.convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
    ) == pytest.approx(37.77777777777778)
    assert temperature_util.convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN
    ) == pytest.approx(310.92777777777775)
    # Interval
    assert temperature_util.convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS, True
    ) == pytest.approx(55.55555555555556)
    assert temperature_util.convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN, True
    ) == pytest.approx(55.55555555555556)


def test_convert_from_kelvin() -> None:
    """Test conversion from K to other units."""
    kelvin = 100
    assert temperature_util.convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.CELSIUS
    ) == pytest.approx(-173.15)
    assert temperature_util.convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.FAHRENHEIT
    ) == pytest.approx(-279.66999999999996)
    # Interval
    assert temperature_util.convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.FAHRENHEIT, True
    ) == pytest.approx(180.0)
    assert temperature_util.convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.KELVIN, True
    ) == pytest.approx(100)
