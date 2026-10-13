"""Test the Anova switches."""

from unittest.mock import AsyncMock

from anova_wifi import CommandFailure
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_init_integration, get_device


@pytest.mark.usefixtures("anova_api")
async def test_switch_is_off_while_idle(hass: HomeAssistant) -> None:
    """Test the cook switch is off while idle."""
    await async_init_integration(hass)
    assert hass.states.get("switch.anova_precision_cooker_cook").state == "off"


@pytest.mark.usefixtures("anova_api_cooking")
async def test_switch_is_on_while_cooking(hass: HomeAssistant) -> None:
    """Test the cook switch is on while a cook is running."""
    await async_init_integration(hass)
    assert hass.states.get("switch.anova_precision_cooker_cook").state == "on"


@pytest.mark.usefixtures("anova_api_unsupported_device_type")
async def test_no_switch_for_unsupported_device_type(hass: HomeAssistant) -> None:
    """Test no switch entity is created for a device type with no command capabilities."""
    await async_init_integration(hass)
    assert hass.states.async_all("switch") == []


@pytest.mark.usefixtures("anova_api")
async def test_turn_on_starts_a_cook_with_pending_values(hass: HomeAssistant) -> None:
    """Test turning the switch on starts a cook using the number entities' values."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.start_cook = AsyncMock()

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.anova_precision_cooker_cook"},
        blocking=True,
    )

    device.start_cook.assert_awaited_once_with(54.72, 0, "C")


@pytest.mark.usefixtures("anova_api_cooking")
async def test_turn_off_stops_the_cook(hass: HomeAssistant) -> None:
    """Test turning the switch off stops the current cook."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.stop_cook = AsyncMock()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.anova_precision_cooker_cook"},
        blocking=True,
    )

    device.stop_cook.assert_awaited_once_with()


@pytest.mark.usefixtures("anova_api_cooking")
async def test_turn_off_failure_raises(hass: HomeAssistant) -> None:
    """Test a CommandFailure while stopping surfaces as HomeAssistantError."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.stop_cook = AsyncMock(side_effect=CommandFailure("boom"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.anova_precision_cooker_cook"},
            blocking=True,
        )
