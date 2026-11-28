"""Tests for the Home Assistant system state conditions."""

import probatio
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition, system_state


async def _evaluate(hass: HomeAssistant, condition_key: str) -> bool | None:
    """Validate and evaluate a system state condition."""
    config = await condition.async_validate_condition_config(
        hass, {"condition": condition_key}
    )
    checker = await condition.async_from_config(hass, config)
    return checker(hass)


async def test_restart_required(hass: HomeAssistant) -> None:
    """Test the restart condition follows the restart flag."""
    assert await _evaluate(hass, "homeassistant.restart_required") is False

    system_state.async_set_home_assistant_restart_required(hass, "hacs")

    assert await _evaluate(hass, "homeassistant.restart_required") is True


async def test_host_reboot_required(hass: HomeAssistant) -> None:
    """Test the reboot condition follows the reboot flag."""
    assert await _evaluate(hass, "homeassistant.host_reboot_required") is False

    system_state.async_set_host_reboot_required(hass, True)

    assert await _evaluate(hass, "homeassistant.host_reboot_required") is True


async def test_rejects_options(hass: HomeAssistant) -> None:
    """Test the conditions do not take options."""
    with pytest.raises(probatio.Invalid):
        await condition.async_validate_condition_config(
            hass,
            {"condition": "homeassistant.restart_required", "options": {"x": 1}},
        )
