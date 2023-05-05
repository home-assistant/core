"""Test Home Assistant pressure utility functions."""
import pytest

from homeassistant.const import UnitOfPressure
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.pressure as pressure_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = UnitOfPressure.PA


def test_raise_deprecation_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure that a warning is raised on use of convert."""
    assert pressure_util.convert(2, UnitOfPressure.PA, UnitOfPressure.PA) == 2
    assert "use unit_conversion.PressureConverter instead" in caplog.text


def test_convert_same_unit() -> None:
    """Test conversion from any unit to same unit."""
    assert pressure_util.convert(2, UnitOfPressure.PA, UnitOfPressure.PA) == 2
    assert pressure_util.convert(3, UnitOfPressure.HPA, UnitOfPressure.HPA) == 3
    assert pressure_util.convert(4, UnitOfPressure.MBAR, UnitOfPressure.MBAR) == 4
    assert pressure_util.convert(5, UnitOfPressure.INHG, UnitOfPressure.INHG) == 5
    assert pressure_util.convert(6, UnitOfPressure.KPA, UnitOfPressure.KPA) == 6
    assert pressure_util.convert(7, UnitOfPressure.CBAR, UnitOfPressure.CBAR) == 7
    assert pressure_util.convert(8, UnitOfPressure.MMHG, UnitOfPressure.MMHG) == 8


def test_convert_invalid_unit() -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        pressure_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        pressure_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value() -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        pressure_util.convert("a", UnitOfPressure.HPA, UnitOfPressure.INHG)


def test_convert_from_hpascals() -> None:
    """Test conversion from hPA to other units."""
    hpascals = 1000
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.PSI
    ) == pytest.approx(14.5037743897)
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.INHG
    ) == pytest.approx(29.5299801647)
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.PA
    ) == pytest.approx(100000)
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.KPA
    ) == pytest.approx(100)
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.MBAR
    ) == pytest.approx(1000)
    assert pressure_util.convert(
        hpascals, UnitOfPressure.HPA, UnitOfPressure.CBAR
    ) == pytest.approx(100)


def test_convert_from_kpascals() -> None:
    """Test conversion from hPA to other units."""
    kpascals = 100
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.PSI
    ) == pytest.approx(14.5037743897)
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.INHG
    ) == pytest.approx(29.5299801647)
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.PA
    ) == pytest.approx(100000)
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.HPA
    ) == pytest.approx(1000)
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.MBAR
    ) == pytest.approx(1000)
    assert pressure_util.convert(
        kpascals, UnitOfPressure.KPA, UnitOfPressure.CBAR
    ) == pytest.approx(100)


def test_convert_from_inhg() -> None:
    """Test conversion from inHg to other units."""
    inhg = 30
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.PSI
    ) == pytest.approx(14.7346266155)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.KPA
    ) == pytest.approx(101.59167)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.HPA
    ) == pytest.approx(1015.9167)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.PA
    ) == pytest.approx(101591.67)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.MBAR
    ) == pytest.approx(1015.9167)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.CBAR
    ) == pytest.approx(101.59167)
    assert pressure_util.convert(
        inhg, UnitOfPressure.INHG, UnitOfPressure.MMHG
    ) == pytest.approx(762)


def test_convert_from_mmhg() -> None:
    """Test conversion from mmHg to other units."""
    inhg = 30
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.PSI
    ) == pytest.approx(0.580103)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.KPA
    ) == pytest.approx(3.99967)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.HPA
    ) == pytest.approx(39.9967)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.PA
    ) == pytest.approx(3999.67)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.MBAR
    ) == pytest.approx(39.9967)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.CBAR
    ) == pytest.approx(3.99967)
    assert pressure_util.convert(
        inhg, UnitOfPressure.MMHG, UnitOfPressure.INHG
    ) == pytest.approx(1.181102)
