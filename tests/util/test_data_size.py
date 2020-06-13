"""Test Home Assistant data_size utility functions."""

import pytest

from homeassistant.const import (
    DATA_BYTES,
    DATA_GIBIBYTES,
    DATA_GIGABYTES,
    DATA_KIBIBYTES,
    DATA_KILOBYTES,
    DATA_MEBIBYTES,
    DATA_MEGABYTES,
    DATA_TEBIBYTES,
    DATA_TERABYTES,
)
import homeassistant.util.data_size as data_size_util

INVALID_SYMBOL = "bob"
VALID_SYMBOL = DATA_BYTES


def test_convert_same_unit():
    """Test conversion from any unit to same unit."""
    assert data_size_util.convert(1, DATA_KILOBYTES, DATA_KILOBYTES) == 1
    assert data_size_util.convert(1.5, DATA_KILOBYTES, DATA_KILOBYTES) == 1.5
    assert data_size_util.convert(1.2345, DATA_KILOBYTES, DATA_KILOBYTES) == 1.2345


def test_convert_invalid_unit():
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        data_size_util.convert(5, INVALID_SYMBOL, VALID_SYMBOL)

    with pytest.raises(ValueError):
        data_size_util.convert(5, VALID_SYMBOL, INVALID_SYMBOL)


def test_convert_nonnumeric_value():
    """Test exception is thrown for non-numeric type."""
    with pytest.raises(TypeError):
        data_size_util.convert("a", DATA_MEGABYTES, DATA_KILOBYTES)


def test_convert_si():
    """Test conversion within SI units."""
    assert data_size_util.convert(1, DATA_KILOBYTES, DATA_BYTES) == 1000
    assert data_size_util.convert(1000, DATA_BYTES, DATA_KILOBYTES) == 1
    assert data_size_util.convert(1024, DATA_BYTES, DATA_KILOBYTES) == 1.024
    assert data_size_util.convert(1000, DATA_MEGABYTES, DATA_GIGABYTES) == 1
    assert data_size_util.convert(1, DATA_GIGABYTES, DATA_KILOBYTES) == 1000000


def test_convert_iec():
    """Test conversion within IEC units."""
    assert data_size_util.convert(1, DATA_KIBIBYTES, DATA_BYTES) == 1024
    assert data_size_util.convert(1024, DATA_BYTES, DATA_KIBIBYTES) == 1
    assert data_size_util.convert(1000, DATA_BYTES, DATA_KIBIBYTES) == 0.9765625
    assert data_size_util.convert(1024, DATA_MEBIBYTES, DATA_GIBIBYTES) == 1
    assert data_size_util.convert(1, DATA_GIBIBYTES, DATA_MEBIBYTES) == 1024
    assert data_size_util.convert(1, DATA_GIBIBYTES, DATA_KIBIBYTES) == 1048576


def test_convert_si_iec():
    """Test conversion from SI to IEC units and vice versa."""
    assert data_size_util.convert(1, DATA_KILOBYTES, DATA_KIBIBYTES) == 0.9765625
    assert data_size_util.convert(1, DATA_KIBIBYTES, DATA_KILOBYTES) == 1.024
    assert data_size_util.convert(0.9765625, DATA_KIBIBYTES, DATA_KILOBYTES) == 1
    assert data_size_util.convert(1.024, DATA_KILOBYTES, DATA_KIBIBYTES) == 1
    assert (
        data_size_util.convert(0.9765625, DATA_KILOBYTES, DATA_KIBIBYTES)
        == 0.95367431640625
    )
    assert data_size_util.convert(1, DATA_TERABYTES, DATA_KIBIBYTES) == 976562500
    assert data_size_util.convert(1, DATA_TEBIBYTES, DATA_GIGABYTES) == 1099.511627776
