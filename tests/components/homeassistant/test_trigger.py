"""Tests for the Home Assistant system state triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import system_state
from homeassistant.setup import async_setup_component


async def _arm(hass: HomeAssistant, trigger: str) -> None:
    """Set up an automation with a system state trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"trigger": trigger},
                "action": {
                    "action": "test.automation",
                    "data": {
                        "description": "{{ trigger.description }}",
                        "sources": "{{ trigger.sources | default([]) }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


async def test_restart_required(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the restart trigger fires once, when the first integration asks."""
    await _arm(hass, "homeassistant.restart_required")

    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    system_state.async_set_home_assistant_restart_required(hass, "demo")
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data == {
        "description": "Home Assistant restart required",
        "sources": ["hacs"],
    }


async def test_restart_required_already_set(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the restart trigger does not fire for a flag set before it attached."""
    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    await _arm(hass, "homeassistant.restart_required")

    system_state.async_set_home_assistant_restart_required(hass, "demo")
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_host_reboot_required(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the reboot trigger fires each time Supervisor raises the flag."""
    await _arm(hass, "homeassistant.host_reboot_required")

    system_state.async_set_host_reboot_required(hass, True)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["description"] == "host reboot required"

    system_state.async_set_host_reboot_required(hass, False)
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    system_state.async_set_host_reboot_required(hass, True)
    await hass.async_block_till_done()
    assert len(service_calls) == 2


@pytest.mark.parametrize(
    "trigger",
    ["homeassistant.restart_required", "homeassistant.host_reboot_required"],
)
async def test_unload(
    hass: HomeAssistant, service_calls: list[ServiceCall], trigger: str
) -> None:
    """Test a turned off automation no longer fires."""
    await _arm(hass, trigger)
    await hass.services.async_call(
        automation.DOMAIN,
        "turn_off",
        {"entity_id": "automation.automation_0"},
        blocking=True,
    )

    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    system_state.async_set_host_reboot_required(hass, True)
    await hass.async_block_till_done()

    # Only the turn_off call itself, the automation did not run.
    assert [call.service for call in service_calls] == ["turn_off"]


async def test_legacy_homeassistant_trigger_still_works(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the legacy homeassistant trigger keeps working next to the new ones."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"trigger": "homeassistant", "event": "shutdown"},
                "action": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    await hass.async_stop()

    assert len(service_calls) == 1
