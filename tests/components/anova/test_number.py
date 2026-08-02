"""Test the Anova numbers."""

from unittest.mock import AsyncMock

from anova_wifi import AnovaCommand, CommandFailure
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_init_integration, get_device
from .conftest import DUMMY_ID


@pytest.mark.usefixtures("anova_api")
async def test_numbers_seeded_from_device_state(hass: HomeAssistant) -> None:
    """Test the numbers are seeded from the device's own last-reported job values."""
    await async_init_integration(hass)
    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "54.72"
    )
    assert hass.states.get("number.anova_precision_cooker_timer").state == "0.0"


@pytest.mark.usefixtures("anova_api_unsupported_device_type")
async def test_no_numbers_for_unsupported_device_type(hass: HomeAssistant) -> None:
    """Test no number entities are created for a device type with no command capabilities."""
    await async_init_integration(hass)
    assert hass.states.async_all("number") == []


@pytest.mark.usefixtures("anova_api")
async def test_setting_target_temperature_while_idle_is_local_only(
    hass: HomeAssistant,
) -> None:
    """Test setting the target temperature while idle just stores it locally."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.send_command = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.anova_precision_cooker_target_temperature",
            "value": 60,
        },
        blocking=True,
    )

    assert (
        hass.states.get("number.anova_precision_cooker_target_temperature").state
        == "60.0"
    )
    device.send_command.assert_not_called()


@pytest.mark.usefixtures("anova_api_cooking")
@pytest.mark.parametrize(
    ("entity_id", "value", "expected_command", "expected_payload"),
    [
        pytest.param(
            "number.anova_precision_cooker_target_temperature",
            65,
            AnovaCommand.CMD_APC_SET_TARGET_TEMP,
            {
                "cookerId": DUMMY_ID,
                "type": "a5",
                "targetTemperature": 65.0,
                "unit": "C",
            },
            id="target_temperature",
        ),
        pytest.param(
            "number.anova_precision_cooker_timer",
            15,
            AnovaCommand.CMD_APC_SET_TIMER,
            {"cookerId": DUMMY_ID, "type": "a5", "timer": 900},
            id="timer_in_minutes",
        ),
    ],
)
async def test_setting_while_cooking_sends_command(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
    expected_command: AnovaCommand,
    expected_payload: dict[str, object],
) -> None:
    """Test setting a number while cooking calls update_running_cook."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    assert device.is_cooking is True
    device.send_command = AsyncMock()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )

    device.send_command.assert_awaited_once_with(expected_command, expected_payload)


@pytest.mark.usefixtures("anova_api_cooking")
async def test_setting_target_temperature_failure_raises(hass: HomeAssistant) -> None:
    """Test a CommandFailure while cooking surfaces as HomeAssistantError."""
    entry = await async_init_integration(hass)
    device = get_device(entry)
    device.send_command = AsyncMock(side_effect=CommandFailure("boom"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.anova_precision_cooker_target_temperature",
                "value": 65,
            },
            blocking=True,
        )
