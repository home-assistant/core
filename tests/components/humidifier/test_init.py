"""The tests for the humidifier component."""

from enum import Enum
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from homeassistant.components import humidifier
from homeassistant.components.humidifier import (
    ATTR_MODE,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant

from tests.common import help_test_all, import_and_test_deprecated_constant_enum


class MockHumidifierEntity(HumidifierEntity):
    """Mock Humidifier device to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_on = MagicMock()
    await humidifier.async_turn_on()

    assert humidifier.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_off = MagicMock()
    await humidifier.async_turn_off()

    assert humidifier.turn_off.called


def _create_tuples(enum: Enum, constant_prefix: str) -> list[tuple[Enum, str]]:
    return [(enum_field, constant_prefix) for enum_field in enum]


@pytest.mark.parametrize(
    "module",
    [humidifier, humidifier.const],
)
def test_all(module: ModuleType) -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(module)


@pytest.mark.parametrize(
    ("enum", "constant_prefix"),
    _create_tuples(humidifier.HumidifierEntityFeature, "SUPPORT_")
    + _create_tuples(humidifier.HumidifierDeviceClass, "DEVICE_CLASS_"),
)
@pytest.mark.parametrize(("module"), [humidifier, humidifier.const])
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: Enum,
    constant_prefix: str,
    module: ModuleType,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, module, enum, constant_prefix, "2025.1"
    )


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockHumidifierEntity(HumidifierEntity):
        _attr_mode = "mode1"

        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockHumidifierEntity()
    assert entity.supported_features_compat is HumidifierEntityFeature(1)
    assert "MockHumidifierEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "HumidifierEntityFeature.MODES" in caplog.text
    caplog.clear()
    assert entity.supported_features_compat is HumidifierEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text

    assert entity.state_attributes[ATTR_MODE] == "mode1"
