"""The tests for the siren component."""

from types import ModuleType
from unittest.mock import MagicMock

import pytest

from homeassistant.components import siren
from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    process_turn_on_params,
)
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.core import HomeAssistant

from tests.common import help_test_all, import_and_test_deprecated_constant_enum


class MockSirenEntity(SirenEntity):
    """Mock siren device to use in tests."""

    _attr_is_on = True

    def __init__(
        self,
        supported_features=0,
        available_tones_as_attr=None,
        available_tones_in_desc=None,
    ):
        """Initialize mock siren entity."""
        self._attr_supported_features = supported_features
        if available_tones_as_attr is not None:
            self._attr_available_tones = available_tones_as_attr
        elif available_tones_in_desc is not None:
            self.entity_description = SirenEntityDescription(
                "mock", available_tones=available_tones_in_desc
            )


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.turn_on = MagicMock()
    await siren.async_turn_on()

    assert siren.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    siren = MockSirenEntity()
    siren.hass = hass

    siren.turn_off = MagicMock()
    await siren.async_turn_off()

    assert siren.turn_off.called


async def test_no_available_tones(hass: HomeAssistant) -> None:
    """Test ValueError when siren advertises tones but has no available_tones."""
    siren = MockSirenEntity(SirenEntityFeature.TONES)
    siren.hass = hass
    with pytest.raises(ValueError):
        process_turn_on_params(siren, {"tone": "test"})


async def test_available_tones_list(hass: HomeAssistant) -> None:
    """Test that valid tones from tone list will get passed in."""
    siren = MockSirenEntity(
        SirenEntityFeature.TONES, available_tones_as_attr=["a", "b"]
    )
    siren.hass = hass
    assert process_turn_on_params(siren, {"tone": "a"}) == {"tone": "a"}


async def test_available_tones(hass: HomeAssistant) -> None:
    """Test different available tones scenarios."""
    siren = MockSirenEntity(
        SirenEntityFeature.TONES, available_tones_in_desc=["a", "b"]
    )
    assert siren.available_tones == ["a", "b"]
    siren = MockSirenEntity(SirenEntityFeature.TONES)
    assert siren.available_tones is None


async def test_available_tones_dict(hass: HomeAssistant) -> None:
    """Test that valid tones from available_tones dict will get passed in."""
    siren = MockSirenEntity(SirenEntityFeature.TONES, {1: "a", 2: "b"})
    siren.hass = hass
    assert process_turn_on_params(siren, {"tone": "a"}) == {"tone": 1}
    assert process_turn_on_params(siren, {"tone": 1}) == {"tone": 1}


async def test_missing_tones_list(hass: HomeAssistant) -> None:
    """Test ValueError when setting a tone that is missing from available_tones list."""
    siren = MockSirenEntity(SirenEntityFeature.TONES, ["a", "b"])
    siren.hass = hass
    with pytest.raises(ValueError):
        process_turn_on_params(siren, {"tone": "test"})


async def test_missing_tones_dict(hass: HomeAssistant) -> None:
    """Test ValueError when setting a tone that is missing from available_tones dict."""
    siren = MockSirenEntity(SirenEntityFeature.TONES, {1: "a", 2: "b"})
    siren.hass = hass
    with pytest.raises(ValueError):
        process_turn_on_params(siren, {"tone": 3})


@pytest.mark.parametrize(
    "module",
    [siren, siren.const],
)
def test_all(module: ModuleType) -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(module)


@pytest.mark.parametrize(("enum"), list(SirenEntityFeature))
@pytest.mark.parametrize(("module"), [siren, siren.const])
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: SirenEntityFeature,
    module: ModuleType,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(caplog, module, enum, "SUPPORT_", "2025.1")


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockSirenEntity(siren.SirenEntity):
        _attr_supported_features = 1

    entity = MockSirenEntity()
    assert entity.supported_features is siren.SirenEntityFeature(1)
    assert "MockSirenEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "SirenEntityFeature.TURN_ON" in caplog.text
    caplog.clear()
    assert entity.supported_features is siren.SirenEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text
