"""Test Home Assistant pressure utility functions."""
import pytest

from homeassistant.const import (
    PRESSURE_CBAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    PRESSURE_PA,
    PRESSURE_PSI,
)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.pressure as pressure_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = PRESSURE_PA


def test_raise_deprecation_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure that a warning is raised on use of convert."""
    assert pressure_util.convert(2, PRESSURE_PA, PRESSURE_PA) == 2
    assert "use unit_conversion.PressureConverter instead" in caplog.text


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert pressure_util.convert(2, PRESSURE_PA, PRESSURE_PA) == 2
    assert pressure_util.convert(3, PRESSURE_HPA, PRESSURE_HPA) == 3
    assert pressure_util.convert(4, PRESSURE_MBAR, PRESSURE_MBAR) == 4
    assert pressure_util.convert(5, PRESSURE_INHG, PRESSURE_INHG) == 5
    assert pressure_util.convert(6, PRESSURE_KPA, PRESSURE_KPA) == 6
    assert pressure_util.convert(7, PRESSURE_CBAR, PRESSURE_CBAR) == 7
    assert pressure_util.convert(8, PRESSURE_MMHG, PRESSURE_MMHG) == 8


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        pressure_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        pressure_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        pressure_util.convert("a", PRESSURE_HPA, PRESSURE_INHG)


def test_convert_from_hpascals():
    """Test conversion from hPA to other units."""
    hpascals = 1000
    assert pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_PSI) == pytest.approx(
        14.5037743897
    )
    assert pressure_util.convert(
        hpascals, PRESSURE_HPA, PRESSURE_INHG
    ) == pytest.approx(29.5299801647)
    assert pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_PA) == pytest.approx(
        100000
    )
    assert pressure_util.convert(hpascals, PRESSURE_HPA, PRESSURE_KPA) == pytest.approx(
        100
    )
    assert pressure_util.convert(
        hpascals, PRESSURE_HPA, PRESSURE_MBAR
    ) == pytest.approx(1000)
    assert pressure_util.convert(
        hpascals, PRESSURE_HPA, PRESSURE_CBAR
    ) == pytest.approx(100)


def test_convert_from_kpascals():
    """Test conversion from hPA to other units."""
    kpascals = 100
    assert pressure_util.convert(kpascals, PRESSURE_KPA, PRESSURE_PSI) == pytest.approx(
        14.5037743897
    )
    assert pressure_util.convert(
        kpascals, PRESSURE_KPA, PRESSURE_INHG
    ) == pytest.approx(29.5299801647)
    assert pressure_util.convert(kpascals, PRESSURE_KPA, PRESSURE_PA) == pytest.approx(
        100000
    )
    assert pressure_util.convert(kpascals, PRESSURE_KPA, PRESSURE_HPA) == pytest.approx(
        1000
    )
    assert pressure_util.convert(
        kpascals, PRESSURE_KPA, PRESSURE_MBAR
    ) == pytest.approx(1000)
    assert pressure_util.convert(
        kpascals, PRESSURE_KPA, PRESSURE_CBAR
    ) == pytest.approx(100)


def test_convert_from_inhg():
    """Test conversion from inHg to other units."""
    inhg = 30
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_PSI) == pytest.approx(
        14.7346266155
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_KPA) == pytest.approx(
        101.59167
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_HPA) == pytest.approx(
        1015.9167
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_PA) == pytest.approx(
        101591.67
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_MBAR) == pytest.approx(
        1015.9167
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_CBAR) == pytest.approx(
        101.59167
    )
    assert pressure_util.convert(inhg, PRESSURE_INHG, PRESSURE_MMHG) == pytest.approx(
        762
    )


def test_convert_from_mmhg():
    """Test conversion from mmHg to other units."""
    inhg = 30
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_PSI) == pytest.approx(
        0.580103
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_KPA) == pytest.approx(
        3.99967
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_HPA) == pytest.approx(
        39.9967
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_PA) == pytest.approx(
        3999.67
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_MBAR) == pytest.approx(
        39.9967
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_CBAR) == pytest.approx(
        3.99967
    )
    assert pressure_util.convert(inhg, PRESSURE_MMHG, PRESSURE_INHG) == pytest.approx(
        1.181102
    )
