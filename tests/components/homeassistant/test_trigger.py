"""Tests for the Home Assistant triggers."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.components.homeassistant.trigger import RestartRequiredTrigger
from homeassistant.config import DATA_PREVIOUS_VERSION
from homeassistant.const import __version__
from homeassistant.core import Context, CoreState, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import system_state
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

UPDATED_AUTOMATION = {
    automation.DOMAIN: {
        "alias": "hello",
        "trigger": {"trigger": "homeassistant.updated"},
        "action": {
            "service": "test.automation",
            "data_template": {
                "description": "{{ trigger.description }}",
                "from_version": "{{ trigger.from_version }}",
                "to_version": "{{ trigger.to_version }}",
            },
        },
    }
}


@pytest.mark.parametrize("hass_config", [UPDATED_AUTOMATION])
@pytest.mark.parametrize(
    "previous_version",
    [
        pytest.param("2026.9.4", id="update"),
        pytest.param("2099.1.0", id="downgrade"),
    ],
)
@pytest.mark.usefixtures("mock_hass_config")
async def test_updated_fires_once(
    hass: HomeAssistant, hass_config: ConfigType, previous_version: str
) -> None:
    """Test the updated trigger fires once after a version change."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)
    hass.data[DATA_PREVIOUS_VERSION] = previous_version

    assert await async_setup_component(hass, automation.DOMAIN, hass_config)
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "description": "Home Assistant updated",
        "from_version": previous_version,
        "to_version": __version__,
    }

    # Armed again after start, so it must stay silent
    await hass.services.async_call(
        automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_updated_not_fired_without_version_change(hass: HomeAssistant) -> None:
    """Test the updated trigger stays silent on a normal start."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(hass, automation.DOMAIN, UPDATED_AUTOMATION)
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(calls) == 0


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


async def test_restart_required_reentrant(hass: HomeAssistant) -> None:
    """Test an action that adds a restart source does not fire the trigger again."""
    trigger = RestartRequiredTrigger(
        hass, TriggerConfig(key="homeassistant.restart_required")
    )
    payloads: list[dict[str, object]] = []

    @callback
    def run_action(
        extra_trigger_payload: dict[str, object],
        description: str,
        context: Context | None = None,
    ) -> asyncio.Task[None]:
        payloads.append(extra_trigger_payload)
        # Actions start eagerly, so this lands while the listener still runs
        system_state.async_set_home_assistant_restart_required(hass, "demo")
        return hass.async_create_task(asyncio.sleep(0))

    unsub = await trigger.async_attach_runner(run_action)
    system_state.async_set_home_assistant_restart_required(hass, "hacs")
    await hass.async_block_till_done()
    unsub()

    assert payloads == [{"sources": ["hacs"]}]


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


@pytest.mark.parametrize("event", ["start", "shutdown"])
async def test_legacy_trigger_still_works(hass: HomeAssistant, event: str) -> None:
    """Test the legacy homeassistant trigger is not taken over by the new one."""
    calls = async_mock_service(hass, "test", "automation")
    hass.set_state(CoreState.not_running)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "homeassistant", "event": event},
                "action": {
                    "service": "test.automation",
                    "data_template": {"event": "{{ trigger.event }}"},
                },
            }
        },
    )
    await hass.async_start()
    await hass.async_block_till_done()
    with patch.object(hass.loop, "stop"):
        await hass.async_stop()

    assert len(calls) == 1
    assert calls[0].data == {"event": event}
