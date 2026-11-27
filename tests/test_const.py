"""Test const module."""

import pytest
from pytest_homeassistant.common import (
    help_test_all,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)

from homeassistant import const
from homeassistant.const import UnitOfDensity, UnitOfRatio


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(
    ("replacement", "constant_name", "breaks_in_version"),
    [
        (
            "p/m³",
            "CONCENTRATION_PARTS_PER_CUBIC_METER",
            "2027.8",
        ),
    ],
)
def test_deprecated_constant(
    caplog: pytest.LogCaptureFixture,
    replacement: str,
    constant_name: str,
    breaks_in_version: str,
) -> None:
    """Test deprecated constants, where no replacement is provided."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        constant_name,
        replacement,
        replacement,
        breaks_in_version,
    )


@pytest.mark.parametrize(
    ("constant_name", "value"),
    [
        ("ATTR_CONFIGURATION_URL", "configuration_url"),
        ("ATTR_CONNECTIONS", "connections"),
        ("ATTR_DEFAULT_NAME", "default_name"),
        ("ATTR_HW_VERSION", "hw_version"),
        ("ATTR_IDENTIFIERS", "identifiers"),
        ("ATTR_MANUFACTURER", "manufacturer"),
        ("ATTR_MODEL", "model"),
        ("ATTR_MODEL_ID", "model_id"),
        ("ATTR_SERIAL_NUMBER", "serial_number"),
        ("ATTR_SUGGESTED_AREA", "suggested_area"),
        ("ATTR_SW_VERSION", "sw_version"),
    ],
)
def test_deprecated_device_info_constant(
    caplog: pytest.LogCaptureFixture, constant_name: str, value: str
) -> None:
    """Test the deprecated device info constants, which have no replacement."""
    import_and_test_deprecated_constant(
        caplog, const, constant_name, None, value, "2027.12"
    )


def test_deprecated_attr_via_device(caplog: pytest.LogCaptureFixture) -> None:
    """Test ATTR_VIA_DEVICE deprecation in favor of via_device_id."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        "ATTR_VIA_DEVICE",
        "via_device_id",
        "via_device",
        "2027.8",
    )


@pytest.mark.parametrize(
    "replacement",
    [
        UnitOfDensity.GRAMS_PER_CUBIC_METER,
        UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
        UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        UnitOfDensity.MICROGRAMS_PER_CUBIC_FOOT,
        UnitOfRatio.PARTS_PER_MILLION,
        UnitOfRatio.PARTS_PER_BILLION,
    ],
)
def test_deprecated_concentration_constant(
    caplog: pytest.LogCaptureFixture,
    replacement: UnitOfDensity | UnitOfRatio,
) -> None:
    """Test deprecated concentration constants replaced by an enum."""
    import_and_test_deprecated_constant_enum(
        caplog,
        const,
        replacement,
        "CONCENTRATION_",
        "2027.8",
    )
