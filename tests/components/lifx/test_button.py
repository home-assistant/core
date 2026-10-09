"""Tests for the LIFX button platform."""

from typing import Any
from unittest.mock import call, patch

from lifx import HSBK, LifxError, Light, LightWaveform
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry
from .helpers import create_mock_light


@pytest.fixture(autouse=True)
def patch_lifx_identify_delay() -> Any:
    """Set the identify flash delay to zero."""
    with patch("homeassistant.components.lifx.coordinator.LIFX_IDENTIFY_DELAY", 0):
        yield


@pytest.fixture
async def loaded_device(hass: HomeAssistant) -> Light:
    """Set up a typed LIFX entry and return its device."""
    device = create_mock_light()
    device.state.power = 65535
    await async_setup_lifx_entry(hass, device)
    return device


@pytest.mark.parametrize(
    ("key", "method", "expected_args", "expected_kwargs"),
    [
        pytest.param("restart", "set_reboot", (), {}, id="restart"),
        pytest.param(
            "identify",
            "set_waveform_optional",
            (HSBK(0, 0, 1, 3500),),
            {"period": 1.0, "cycles": 3, "waveform": LightWaveform.SINE},
            id="identify",
        ),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    loaded_device: Light,
    key: str,
    method: str,
    expected_args: tuple[Any, ...],
    expected_kwargs: dict[str, Any],
) -> None:
    """Test that each button press awaits its public device method."""
    entity_id = f"button.my_group_my_bulb_{key}"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == f"{SERIAL}_{key}"

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    getattr(loaded_device, method).assert_awaited_once_with(
        *expected_args, **expected_kwargs
    )


async def test_identify_powers_a_dark_bulb_on_and_off(
    hass: HomeAssistant, loaded_device: Light
) -> None:
    """Test identifying a powered-off bulb turns it on so the flash is visible."""
    loaded_device.state.power = 0

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {ATTR_ENTITY_ID: "button.my_group_my_bulb_identify"},
        blocking=True,
    )

    loaded_device.set_waveform_optional.assert_awaited_once()
    assert loaded_device.set_power.await_args_list == [
        call(True, duration=1.0),
        call(False, duration=1.0),
    ]


@pytest.mark.parametrize(
    ("key", "method"),
    [
        pytest.param("restart", "set_reboot", id="restart"),
        pytest.param("identify", "set_waveform_optional", id="identify"),
    ],
)
async def test_button_library_error_becomes_home_assistant_error(
    hass: HomeAssistant,
    loaded_device: Light,
    key: str,
    method: str,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    getattr(loaded_device, method).side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: f"button.my_group_my_bulb_{key}"},
            blocking=True,
        )
